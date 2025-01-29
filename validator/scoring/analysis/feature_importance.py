from typing import TYPE_CHECKING, Dict, List, Optional
import numpy as np
import pandas as pd
import torch
import shap
from tqdm import tqdm
from time import time
from interfaces.types import Tweet
from validator.config.hardware_config import HardwareConfig
from validator.config.scoring_config import ScoringWeights
from validator.scoring.scorers.engagement_scorer import EngagementScorer
from validator.scoring.scorers.follower_scorer import FollowerScorer
from validator.scoring.scorers.verification_scorer import VerificationScorer
from validator.scoring.strategies.default_strategy import DefaultScoringStrategy

if TYPE_CHECKING:
    from validator.scoring.agent_scorer import AgentScorer
    from validator.scoring.scorers.semantic_scorer import SemanticScorer

class FeatureImportanceCalculator:
    """Calculates feature importance using SHAP values"""
    
    # Core features definition at class level for consistency
    CORE_FEATURES = [
        'text_length_ratio', 
        'semantic_score', 
        'follower_score', 
        'is_verified',
        'engagement_replies', 
        'engagement_likes', 
        'engagement_retweets', 
        'engagement_views'
    ]

    def __init__(self, 
                 config: HardwareConfig, 
                 weights: ScoringWeights, 
                 semantic_scorer: "SemanticScorer"):
        self.config = config
        self.weights = weights
        self.semantic_scorer = semantic_scorer
        self.engagement_scorer = EngagementScorer(self.weights)
        self.follower_scorer = FollowerScorer(self.weights)
        self.verification_scorer = VerificationScorer(self.weights)
        self.scoring_strategy = DefaultScoringStrategy(self.weights)
        self.device = torch.device(self.config.device_type)

    def _prepare_features(self, posts: List[Tweet]) -> pd.DataFrame:
        """Prepare feature DataFrame from posts"""
        # Calculate semantic scores first
        texts = [str(post.get('Text', '')) for post in posts]
        semantic_scores = self.semantic_scorer.calculate_scores(texts)
        
        # Prepare features using dedicated scorers
        features = []
        for post, semantic_score in zip(posts, semantic_scores):
            # Use dedicated scorers for each component
            follower_score = self.follower_scorer.calculate_score(post)
            
            # Calculate engagement components using engagement scorer
            engagement_components = {
                f"engagement_{key.lower()}": post.get(key, 0) * weight
                for key, weight in self.weights.engagement_weights.items()
            }
            
            # Basic features
            feature_dict = {
                'text_length_ratio': min(len(str(post.get('Text', ''))), 280) / 280,
                'semantic_score': semantic_score,
                'follower_score': follower_score,
                'is_verified': float(post.get('IsVerified', False)),
                **engagement_components
            }
            features.append(feature_dict)
        
        # Ensure features are ordered according to CORE_FEATURES
        df = pd.DataFrame(features)
        return df[self.CORE_FEATURES]  # Enforce consistent column order

    def _score_function(self, X: np.ndarray) -> np.ndarray:
        """Score function for SHAP explainer - use default scoring strategy"""
        # Use consistent feature ordering
        df = pd.DataFrame(X, columns=self.CORE_FEATURES)
        
        # Calculate scores using the same strategy as agent_scorer
        scores = []
        for _, row in df.iterrows():
            score = self.scoring_strategy.calculate_post_score(
                semantic_score=row['semantic_score'],
                engagement_score=sum(
                    row[f'engagement_{key.lower()}'] 
                    for key in self.weights.engagement_weights.keys()
                ),
                follower_score=row['follower_score'],
                text_length_ratio=row['text_length_ratio'],
                is_verified=bool(row['is_verified'] > 0.5)
            )
            scores.append(score)
            
        return np.array(scores)

    def calculate(self, posts: List[Tweet], progress_bar: Optional[tqdm] = None) -> Dict[str, float]:
        """Calculate feature importance using SHAP values"""
        if len(posts) > self.config.max_samples:
            posts = np.random.choice(posts, self.config.max_samples, replace=False)

        df = self._prepare_features(posts)
        if df.empty:
            return {}

        explainer = shap.KernelExplainer(
            self._score_function,
            shap.sample(df, self.config.shap_background_samples).astype(np.float32),
            l1_reg=f'num_features({len(df.columns)})'
        )
        
        shap_values = explainer.shap_values(
            df.astype(np.float32),
            nsamples=self.config.shap_nsamples
        )
        
        if progress_bar:
            progress_bar.update(self.config.shap_background_samples)
            progress_bar.set_postfix({
                "samples": f"{self.config.shap_background_samples}/{self.config.shap_background_samples}",
                "features": ",".join(df.columns)
            })

        # Calculate absolute mean SHAP values
        importance_values = {
            feature: float(np.abs(shap_values[:, i]).mean())
            for i, feature in enumerate(df.columns)
        }
        
        return importance_values
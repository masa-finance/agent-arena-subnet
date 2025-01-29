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

if TYPE_CHECKING:
    from validator.scoring.agent_scorer import AgentScorer
    from validator.scoring.scorers.semantic_scorer import SemanticScorer

class FeatureImportanceCalculator:
    """Calculates feature importance using SHAP values"""

    def __init__(self, 
                 config: HardwareConfig, 
                 weights: ScoringWeights, 
                 semantic_scorer: "SemanticScorer"):
        self.config = config
        self.weights = weights
        self.semantic_scorer = semantic_scorer
        self.device = torch.device(self.config.device_type)

    def _prepare_features(self, posts: List[Tweet]) -> pd.DataFrame:
        """Prepare feature DataFrame from posts"""
        # Calculate semantic scores first
        texts = [str(post.get('Text', '')) for post in posts]
        semantic_scores = self.semantic_scorer.calculate_scores(texts)
        
        # Prepare features without applying weights yet
        features = []
        for post, semantic_score in zip(posts, semantic_scores):
            # Calculate engagement components
            engagement_components = {
                f"engagement_{key.lower()}": post.get(key, 0) * weight
                for key, weight in self.weights.engagement_weights.items()
            }
            
            # Calculate follower score with dampening
            followers = post.get('FollowersCount', 0)
            follower_score = min(
                np.log1p(max(followers, 0)) / self.weights.followers_cap,
                1.0
            ) ** self.weights.followers_dampening
            
            # Basic features
            feature_dict = {
                'text_length_ratio': min(len(str(post.get('Text', ''))), 280) / 280,
                'semantic_score': semantic_score,
                'follower_score': follower_score,
                'is_verified': float(post.get('IsVerified', False)),
                **engagement_components
            }
            features.append(feature_dict)
        
        return pd.DataFrame(features)

    def _score_function(self, X: np.ndarray) -> np.ndarray:
        """Score function for SHAP explainer - apply weights here"""
        df = pd.DataFrame(X, columns=[
            'text_length_ratio', 'semantic_score', 'follower_score', 'is_verified',
            'engagement_replies', 'engagement_likes', 'engagement_retweets', 'engagement_views'
        ])
        
        # Calculate combined engagement score
        engagement_score = df[[c for c in df.columns if c.startswith('engagement_')]].sum(axis=1)
        
        # Apply weights and scaling
        scores = (
            df['text_length_ratio'] * (self.weights.length_weight * self.weights.length_ratio) +
            np.power(df['semantic_score'], 0.75) * (self.weights.semantic_weight * self.weights.semantic_ratio) +
            df['follower_score'] * self.weights.follower_ratio +
            engagement_score * self.weights.engagement_ratio
        )
        
        # Apply semantic quality multiplier
        scores = scores * (1.0 + (df['semantic_score'] * 0.5))
        
        # Apply verification scaling
        verified_mask = df['is_verified'] > 0.5
        scores[verified_mask] = 0.1 + (scores[verified_mask] * 0.9)  # Scale to 0.1-1.0
        scores[~verified_mask] = scores[~verified_mask] * 0.1  # Scale to 0-0.1
        
        return scores

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
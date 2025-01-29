from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import torch
import shap
from tqdm import tqdm
from time import time
from interfaces.types import Tweet
from validator.config.hardware_config import HardwareConfig
from validator.config.scoring_config import ScoringWeights
from validator.scoring.scorers.semantic_scorer import SemanticScorer

class FeatureImportanceCalculator:
    """Calculates feature importance using SHAP values"""

    def __init__(self, config: HardwareConfig, weights: ScoringWeights, semantic_scorer: SemanticScorer):
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
        features = [{
            'text_length': len(str(post.get('Text', ''))),
            'semantic_score': semantic_score,
            'engagement_score': (
                post.get('Likes', 0) * self.weights.engagement_weights['Likes'] +
                post.get('Retweets', 0) * self.weights.engagement_weights['Retweets'] +
                post.get('Replies', 0) * self.weights.engagement_weights['Replies'] +
                post.get('Views', 0) * self.weights.engagement_weights['Views']
            )
        } for post, semantic_score in zip(posts, semantic_scores)]
        
        return pd.DataFrame(features)

    def _score_function(self, X: np.ndarray) -> np.ndarray:
        """Score function for SHAP explainer - apply weights here"""
        df = pd.DataFrame(X, columns=['text_length', 'semantic_score', 'engagement_score'])
        return np.array([np.log1p(
            (row['text_length'] / 280) * (self.weights.length_weight * 0.1 * 0.05) +
            np.power(row['semantic_score'], 0.75) * (self.weights.semantic_weight * 2.0 * 0.8) +
            row['engagement_score'] * 0.15
        ) * (1.0 + (row['semantic_score'] * 0.5)) for _, row in df.iterrows()])

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
            l1_reg='num_features(3)'  # Explicitly set to match our 3 features
        )
        
        shap_values = explainer.shap_values(
            df.astype(np.float32),
            nsamples=self.config.shap_nsamples
        )
        
        if progress_bar:
            progress_bar.update(self.config.shap_background_samples)
            progress_bar.set_postfix({
                "samples": f"{self.config.shap_background_samples}/{self.config.shap_background_samples}",
                "features": "text_length,semantic_score,engagement_score"
            })

        # Calculate absolute mean SHAP values
        importance_values = {
            feature: float(np.abs(shap_values[:, i]).mean())
            for i, feature in enumerate(df.columns)
        }
        
        return importance_values 
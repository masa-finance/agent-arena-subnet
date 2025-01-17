from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import torch
import shap
from tqdm import tqdm
from time import time
from interfaces.types import Tweet
from ..config.hardware_config import HardwareConfig
from ..config.scoring_config import ScoringWeights

class FeatureImportanceCalculator:
    """Calculates feature importance using SHAP values"""

    def __init__(self, config: HardwareConfig, weights: ScoringWeights):
        self.config = config
        self.weights = weights
        self.device = torch.device(self.config.device_type)

    def _prepare_features(self, posts: List[Tweet]) -> pd.DataFrame:
        """Prepare feature DataFrame from posts"""
        features = [{
            'text_length': len(str(post.get('Text', ''))),
            'likes': post.get('Likes', 0),
            'retweets': post.get('Retweets', 0),
            'replies': post.get('Replies', 0),
            'views': post.get('Views', 0),
        } for post in posts]
        return pd.DataFrame(features)

    def _score_function(self, X: np.ndarray) -> np.ndarray:
        """Score function for SHAP explainer"""
        X_tensor = torch.tensor(X, device=self.device, dtype=torch.float32)
        return np.array([np.log1p(
            row['text_length'] * self.weights.length_weight +
            row['likes'] * self.weights.engagement_weights['Likes'] +
            row['retweets'] * self.weights.engagement_weights['Retweets'] +
            row['replies'] * self.weights.engagement_weights['Replies'] +
            row['views'] * self.weights.engagement_weights['Views']
        ) for _, row in pd.DataFrame(X, columns=['text_length', 'likes', 'retweets', 'replies', 'views']).iterrows()])

    def calculate(self, posts: List[Tweet], progress_bar: Optional[tqdm] = None) -> Dict[str, float]:
        """Calculate feature importance using SHAP values"""
        start_time = time()
        processed_samples = 0
        
        if len(posts) > self.config.max_samples:
            posts = np.random.choice(posts, self.config.max_samples, replace=False)

        df = self._prepare_features(posts)
        if df.empty:
            return {}

        explainer = shap.KernelExplainer(
            self._score_function,
            shap.sample(df, self.config.shap_background_samples).astype(np.float32),
            l1_reg='num_features(10)'
        )
        
        shap_values = explainer.shap_values(
            df.astype(np.float32),
            nsamples=self.config.shap_nsamples
        )
        
        if progress_bar:
            processed_samples = self.config.shap_background_samples
            elapsed_time = time() - start_time
            rate = processed_samples / elapsed_time if elapsed_time > 0 else 0
            
            progress_bar.update(processed_samples)
            progress_bar.set_postfix({
                "samples": f"{processed_samples}/{self.config.shap_background_samples}",
                "rate": f"{rate:.2f} samples/s"
            })

        return {
            feature: float(np.abs(shap_values[:, i]).mean())
            for i, feature in enumerate(df.columns)
        } 
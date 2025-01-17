from typing import Dict
from interfaces.types import Tweet
from .base_scorer import BaseScorer
from ..config.scoring_config import ScoringWeights
import numpy as np

class EngagementScorer(BaseScorer):
    """Calculates engagement scores based on configured weights"""

    def __init__(self, weights: ScoringWeights):
        self.weights = weights

    def calculate_score(self, post: Tweet) -> float:
        """Calculate engagement score with additional quality metrics"""
        base_score = 0
        for metric, weight in self.weights.engagement_weights.items():
            value = post.get(metric, 0)
            
            # Apply logarithmic scaling to prevent manipulation
            if value > 0:
                value = np.log1p(value)
            
            # Bonus for balanced engagement
            if metric == 'Replies' and value > 0:
                replies_to_likes_ratio = post.get('Replies', 0) / max(post.get('Likes', 1), 1)
                if 0.1 <= replies_to_likes_ratio <= 2.0:  # Healthy conversation ratio
                    value *= 1.2
            
            base_score += value * weight
            
        return base_score 
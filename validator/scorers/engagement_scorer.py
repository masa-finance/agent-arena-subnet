from typing import Dict
from interfaces.types import Tweet
from .base_scorer import BaseScorer
from ..config.scoring_config import ScoringWeights

class EngagementScorer(BaseScorer):
    """Calculates engagement scores based on configured weights"""

    def __init__(self, weights: ScoringWeights):
        self.weights = weights

    def calculate_score(self, post: Tweet) -> float:
        """Calculate engagement score for a single post"""
        score = 0
        for metric, weight in self.weights.engagement_weights.items():
            value = post.get(metric, 0)
            score += value * weight
        return score 
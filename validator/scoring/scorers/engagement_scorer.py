from typing import Dict
from interfaces.types import Tweet
from validator.scoring.scorers.base_scorer import BaseScorer
import numpy as np

class EngagementScorer(BaseScorer):
    """Calculates engagement scores based on configured weights and metrics.
    
    This scorer evaluates post engagement by considering various social metrics
    (likes, replies, etc.) with configurable weights. It also includes a bonus
    multiplier for posts that demonstrate healthy conversation patterns based
    on reply-to-likes ratios.

    The scoring process:
    1. Applies logarithmic scaling to raw engagement numbers
    2. Combines weighted metrics into a base score
    3. Optionally applies a healthy conversation bonus
    """

    def calculate_score(self, post: Tweet) -> float:
        """Calculate engagement score with additional quality metrics.

        Computes a weighted score based on engagement metrics and applies
        a healthy conversation bonus when appropriate reply-to-likes ratios
        are detected.

        Args:
            post (Tweet): The post object containing engagement metrics
                Expected metrics include: Likes, Replies, and other
                engagement-related fields defined in weights.engagement_weights

        Returns:
            float: The calculated engagement score. Higher scores indicate
                stronger and healthier engagement patterns.

        Note:
            - Engagement metrics are log-transformed to handle varying scales
            - A healthy conversation bonus is applied when the ratio of replies
              to likes falls within configured thresholds
        """
        base_score = 0
        
        # Calculate weighted engagement metrics
        for metric, weight in self.weights.engagement_weights.items():
            value = post.get(metric, 0)
            if value > 0:
                value = np.log1p(value)
            base_score += value * weight
        
        # Apply healthy conversation bonus
        if post.get('Replies', 0) > 0:
            replies_to_likes_ratio = post.get('Replies', 0) / max(post.get('Likes', 1), 1)
            if (self.weights.healthy_reply_ratio_min <= 
                replies_to_likes_ratio <= 
                self.weights.healthy_reply_ratio_max):
                base_score *= self.weights.healthy_conversation_bonus
            
        return base_score 
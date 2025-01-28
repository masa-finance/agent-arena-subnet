from typing import Dict
from interfaces.types import Tweet
from validator.scoring.scorers.base_scorer import BaseScorer
import numpy as np

class EngagementScorer(BaseScorer):
    """Calculates engagement scores based on configured weights"""

    def calculate_score(self, post: Tweet) -> float:
        """Calculate engagement score with additional quality metrics"""
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
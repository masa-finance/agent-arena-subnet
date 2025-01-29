from typing import Any
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

class FollowerScorer(BaseScorer):
    """Evaluates profiles based on follower metrics.
    
    This scorer normalizes follower counts using logarithmic scaling and applies
    configurable dampening to prevent mega-accounts from dominating scores.
    """
    
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate normalized follower score.

        Args:
            post (Tweet): Post object containing author profile information
            **kwargs: Additional arguments (unused)

        Returns:
            float: Normalized follower score between 0.0 and 1.0
        """
        try:
            followers_count = post.get("FollowersCount", 0)
            if followers_count <= 0:
                return 0.0
                
            log_followers = np.log1p(followers_count)
            normalized = min(1.0, log_followers / self.weights.followers_cap)
            return normalized * self.weights.followers_dampening
            
        except Exception as e:
            logger.error(f"Error calculating follower score: {str(e)}")
            return 0.0 
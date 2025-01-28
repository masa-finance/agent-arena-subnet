from typing import Optional, Any
from dataclasses import dataclass
from fiber.logging_utils import get_logger
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet

logger = get_logger(__name__)

@dataclass
class ProfileScoreWeights:
    """Weights for different profile scoring components"""
    followers_weight: float = 0.6
    verified_weight: float = 0.4

class ProfileScorer(BaseScorer):
    """Profile scorer that evaluates X/Twitter profiles"""
    
    def __init__(self, weights: Optional[ProfileScoreWeights] = None):
        self.weights = weights or ProfileScoreWeights()
    
    def _normalize_followers(self, followers_count: int) -> float:
        """
        Normalize followers count using log scale with stricter thresholds
        """
        if followers_count <= 0:
            return 0.0
            
        # Use log scale with lower cap
        log_followers = np.log1p(followers_count)
        # Cap at 100k followers (ln(100000) ≈ 11.5)
        normalized = min(1.0, log_followers / 11.5)
        return normalized * 0.6  # Stronger dampening factor
    
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate profile score from post data"""
        followers_count = post.get("FollowersCount", 0)
        is_verified = post.get("IsVerified", False)
        
        try:
            # Calculate component scores
            followers_score = self._normalize_followers(followers_count)
            verified_score = float(is_verified)
            
            # Calculate final score without verification penalty
            final_score = (
                followers_score * self.weights.followers_weight +
                verified_score * self.weights.verified_weight
            )
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating profile score: {str(e)}")
            return 0.0

    def get_score_components(self,
                           followers_count: int,
                           is_verified: bool) -> dict:
        """
        Get detailed breakdown of score components
        
        Args:
            followers_count: Number of followers
            is_verified: Whether the profile is verified
            
        Returns:
            dict: Component scores and weights
        """
        followers_score = self._normalize_followers(followers_count)
        verified_score = float(is_verified)
        
        return {
            "followers": {
                "raw_count": followers_count,
                "normalized_score": followers_score,
                "weight": self.weights.followers_weight,
                "weighted_score": followers_score * self.weights.followers_weight
            },
            "verified": {
                "is_verified": is_verified,
                "score": verified_score,
                "weight": self.weights.verified_weight,
                "weighted_score": verified_score * self.weights.verified_weight
            },
            "total_score": self.calculate_score(post={"FollowersCount": followers_count, "IsVerified": is_verified})
        } 
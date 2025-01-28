from typing import Any, Dict
from fiber.logging_utils import get_logger
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet

logger = get_logger(__name__)

class ProfileScorer(BaseScorer):
    """Profile scorer that evaluates X/Twitter profiles"""
    
    def _normalize_followers(self, followers_count: int) -> float:
        """Normalize followers count using log scale with configured thresholds"""
        if followers_count <= 0:
            return 0.0
            
        log_followers = np.log1p(followers_count)
        normalized = min(1.0, log_followers / self.weights.followers_cap)
        return normalized * self.weights.followers_dampening
    
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate profile score from post data"""
        try:
            followers_count = post.get("FollowersCount", 0)
            is_verified = post.get("IsVerified", False)
            
            # Calculate component scores
            followers_score = self._normalize_followers(followers_count)
            verified_score = float(is_verified)
            
            # Calculate weighted score
            final_score = (
                followers_score * self.weights.profile_weights["followers_weight"] +
                verified_score * self.weights.profile_weights["verified_weight"]
            )
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating profile score: {str(e)}")
            return 0.0

    def get_score_components(self, followers_count: int, is_verified: bool) -> Dict:
        """Get detailed breakdown of score components"""
        followers_score = self._normalize_followers(followers_count)
        verified_score = float(is_verified)
        
        return {
            "followers": {
                "raw_count": followers_count,
                "normalized_score": followers_score,
                "weight": self.weights.profile_weights["followers_weight"],
                "weighted_score": followers_score * self.weights.profile_weights["followers_weight"]
            },
            "verified": {
                "is_verified": is_verified,
                "score": verified_score,
                "weight": self.weights.profile_weights["verified_weight"],
                "weighted_score": verified_score * self.weights.profile_weights["verified_weight"]
            },
            "total_score": self.calculate_score(
                post={"FollowersCount": followers_count, "IsVerified": is_verified}
            )
        } 
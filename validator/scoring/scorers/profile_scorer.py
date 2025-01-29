"""DEPRECATED: This module is being replaced by separate FollowerScorer and VerificationScorer modules."""
from typing import Any, Dict
from fiber.logging_utils import get_logger
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet
import warnings

logger = get_logger(__name__)

class ProfileScorer(BaseScorer):
    """DEPRECATED: Use FollowerScorer and VerificationScorer instead.
    
    This class is maintained for backward compatibility but will be removed in a future version.
    Please migrate to using the separate scorer components.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ProfileScorer is deprecated. Use FollowerScorer and VerificationScorer instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)
    
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """DEPRECATED: Calculate combined profile score.
        
        This method maintains backward compatibility by calculating scores using
        the old weighting system. New code should use separate scorers.
        """
        try:
            followers_count = post.get("FollowersCount", 0)
            is_verified = post.get("IsVerified", False)
            
            # Calculate using follower cap and dampening from new config
            followers_score = self._normalize_followers(followers_count)
            verified_score = float(is_verified)
            
            # Use fixed weights for backward compatibility
            final_score = (followers_score * 0.6) + (verified_score * 0.4)
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating profile score: {str(e)}")
            return 0.0

    def _normalize_followers(self, followers_count: int) -> float:
        """DEPRECATED: Use FollowerScorer.calculate_score() instead."""
        if followers_count <= 0:
            return 0.0
            
        log_followers = np.log1p(followers_count)
        normalized = min(1.0, log_followers / self.weights.followers_cap)
        return normalized * self.weights.followers_dampening

    def get_score_components(self, followers_count: int, is_verified: bool) -> Dict:
        """Get detailed breakdown of score components.

        Provides transparency into the scoring process by returning detailed
        information about each component's contribution to the final score.

        Args:
            followers_count (int): Number of followers
            is_verified (bool): Whether the profile is verified

        Returns:
            Dict: Detailed breakdown containing:
                - Raw and normalized follower scores
                - Verification status and score
                - Component weights
                - Weighted scores for each component
                - Total combined score
        """
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
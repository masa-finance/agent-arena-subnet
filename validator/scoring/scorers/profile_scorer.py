from typing import Any, Dict
from fiber.logging_utils import get_logger
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet

logger = get_logger(__name__)

class ProfileScorer(BaseScorer):
    """Profile scorer that evaluates X/Twitter profiles based on key metrics.
    
    This scorer evaluates user profiles based on two main components:
    1. Follower count (normalized on a logarithmic scale)
    2. Verification status
    
    The final score is a weighted combination of these components, with
    configurable weights and dampening factors to prevent extreme scores.
    """
    
    def _normalize_followers(self, followers_count: int) -> float:
        """Normalize followers count using log scale with configured thresholds.
        
        Applies logarithmic scaling to handle the wide range of follower counts
        and dampens the result to prevent oversized influence from mega-accounts.

        Args:
            followers_count (int): Raw count of followers

        Returns:
            float: Normalized score between 0.0 and 1.0, dampened according to
                configured weights
        """
        if followers_count <= 0:
            return 0.0
            
        log_followers = np.log1p(followers_count)
        normalized = min(1.0, log_followers / self.weights.followers_cap)
        return normalized * self.weights.followers_dampening
    
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate profile score from post data.

        Combines normalized follower count and verification status into a
        weighted profile score.

        Args:
            post (Tweet): Post object containing author profile information
            **kwargs: Additional arguments (unused)

        Returns:
            float: Combined profile score between 0.0 and 1.0. Returns 0.0
                if an error occurs during calculation.
        """
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
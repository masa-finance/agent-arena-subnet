from typing import Optional
from dataclasses import dataclass
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

@dataclass
class ProfileScoreWeights:
    """Weights for different profile scoring components"""
    followers_weight: float = 0.7
    verified_weight: float = 0.3

class ProfileScorer:
    """
    Simple profile scorer that evaluates X/Twitter profiles based on:
    - Followers count
    - Verification status
    
    Can be used standalone or integrated with AgentScorer.
    """
    
    def __init__(self, weights: Optional[ProfileScoreWeights] = None):
        """
        Initialize the profile scorer
        
        Args:
            weights: Optional custom weights for scoring components
        """
        self.weights = weights or ProfileScoreWeights()
        
    def _normalize_followers(self, followers_count: int) -> float:
        """
        Normalize followers count using log scale to handle large ranges
        
        Args:
            followers_count: Raw number of followers
            
        Returns:
            float: Normalized score between 0 and 1
        """
        if followers_count <= 0:
            return 0.0
            
        # Log scale normalization with reasonable caps
        # Assumes 1M followers is max "normal" range
        normalized = min(1.0, (followers_count + 1) / 1_000_000)
        return normalized
        
    def calculate_score(self, 
                       followers_count: int,
                       is_verified: bool) -> float:
        """
        Calculate profile score based on followers and verification
        
        Args:
            followers_count: Number of followers
            is_verified: Whether the profile is verified
            
        Returns:
            float: Profile score between 0 and 1
        """
        try:
            # Calculate component scores
            followers_score = self._normalize_followers(followers_count)
            verified_score = float(is_verified)
            
            # Combine weighted components
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
            "total_score": self.calculate_score(followers_count, is_verified)
        } 
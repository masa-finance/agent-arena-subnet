from typing import Dict, Tuple
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

class VerificationScorer(BaseScorer):
    """
    Handles verification-based score adjustments to ensure verified accounts
    maintain higher scores than unverified accounts.
    """
    
    def scale_scores(self, 
                    verified_scores: Dict[int, float], 
                    unverified_scores: Dict[int, float]) -> Tuple[Dict[int, float], Dict[int, float]]:
        """
        Scale scores to ensure verified accounts always score higher than unverified.
        
        Args:
            verified_scores: Dict of verified account scores by UID
            unverified_scores: Dict of unverified account scores by UID
            
        Returns:
            Tuple of (verified_scores, unverified_scores) after scaling
        """
        if not verified_scores:
            return verified_scores, unverified_scores

        try:
            # Ensure verified scores meet minimum threshold
            min_verified = max(min(verified_scores.values()), 
                             self.weights.verification.minimum_score)
            
            verified_scores = {
                uid: max(score, self.weights.verification.minimum_score) 
                for uid, score in verified_scores.items()
            }

            # Scale unverified scores to be below minimum verified
            if unverified_scores:
                max_unverified = max(unverified_scores.values())
                if max_unverified > 0:
                    target_max = min_verified * self.weights.verification.unverified_cap
                    scale_factor = target_max / max_unverified
                    unverified_scores = {
                        uid: score * scale_factor 
                        for uid, score in unverified_scores.items()
                    }

            return verified_scores, unverified_scores
            
        except Exception as e:
            logger.error(f"Error scaling verification scores: {str(e)}")
            return verified_scores, unverified_scores

    def calculate_score(self, post: Tweet) -> float:
        """
        Required implementation of BaseScorer.calculate_score.
        Not used directly for verification scoring.
        """
        return float(post.get("IsVerified", False)) 
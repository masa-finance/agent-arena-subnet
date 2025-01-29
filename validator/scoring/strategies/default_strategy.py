from typing import Dict
import numpy as np
from validator.scoring.strategies.base_strategy import BaseScoringStrategy

class DefaultScoringStrategy(BaseScoringStrategy):
    """Default implementation of scoring strategy.
    
    This strategy calculates post scores based on multiple weighted factors including
    semantic relevance, engagement metrics, profile strength, and text length.
    It also provides score normalization using kurtosis-based distribution.
    """
    def calculate_post_score(self,
                           semantic_score: float,
                           engagement_score: float,
                           profile_score: float,
                           text_length_ratio: float,
                           is_verified: bool) -> float:
        """Calculate the final score for a post based on multiple weighted factors.

        Args:
            semantic_score (float): The semantic relevance score (0.0-1.0)
            engagement_score (float): The engagement metrics score
            profile_score (float): The profile strength score (0.0-1.0)
            text_length_ratio (float): The ratio of text length to ideal length
            is_verified (bool): Whether the post author is verified

        Returns:
            float: The calculated post score:
                - For verified users: scaled between 0.1-1.0
                - For unverified users: scaled between 0.0-0.1
        """
        # Calculate component scores with weights
        length_score = text_length_ratio * (self.weights.length_weight * 0.1)
        engagement_score = min(engagement_score, 1.0) * self.weights.engagement_multiplier
        weighted_semantic = semantic_score * (self.weights.semantic_weight * self.weights.semantic_multiplier)
        
        # Combine base scores
        base_score = (
            weighted_semantic * self.weights.semantic_ratio +
            engagement_score * self.weights.engagement_ratio +
            profile_score * self.weights.profile_ratio +
            length_score * self.weights.length_ratio
        )
        
        # Apply semantic quality multiplier
        quality_multiplier = 1.0 + (semantic_score * 0.5)
        initial_score = base_score * quality_multiplier
        
        # Apply verification scaling
        if is_verified:
            return 0.1 + (initial_score * 0.9)  # Scale to 0.1-1.0
        else:
            return initial_score * 0.1  # Scale to 0-0.1

    def normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Apply kurtosis-based normalization to a dictionary of scores.

        Normalizes the score distribution using a sigmoid function with kurtosis
        factor to create a more balanced distribution of scores.

        Args:
            scores (Dict[int, float]): Dictionary mapping user IDs to raw scores

        Returns:
            Dict[int, float]: Dictionary of normalized scores maintaining the same
                ID mapping but with adjusted score values. Returns original scores
                if the input is empty or all scores are identical.
        """
        if not scores:
            return scores
            
        scores_array = np.array(list(scores.values()))
        min_score = scores_array.min()
        max_score = scores_array.max()
        
        if max_score <= min_score:
            return scores
            
        kurtosis_factor = 3.0
        final_scores = {}
        
        for uid, score in scores.items():
            normalized_score = (score - min_score) / (max_score - min_score)
            curved_score = 1 / (1 + np.exp(-kurtosis_factor * (normalized_score - 0.5)))
            final_scores[uid] = min_score + (curved_score * (max_score - min_score))
            
        return final_scores 
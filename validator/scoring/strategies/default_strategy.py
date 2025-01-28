from typing import Dict
import numpy as np
from validator.strategies.base_strategy import BaseScoringStrategy

class DefaultScoringStrategy(BaseScoringStrategy):
    """Default implementation of scoring strategy"""
    def calculate_post_score(self,
                           semantic_score: float,
                           engagement_score: float,
                           profile_score: float,
                           text_length_ratio: float,
                           is_verified: bool) -> float:
        # Calculate component scores with weights
        length_score = text_length_ratio * (self.weights.length_weight * 0.1)
        engagement_score = min(engagement_score, 1.0)
        weighted_semantic = semantic_score * (self.weights.semantic_weight * 2.0)
        
        # Combine base scores
        base_score = (
            weighted_semantic * 0.7 +     # 70% semantic
            engagement_score * 0.15 +     # 15% engagement
            profile_score * 0.1 +         # 10% profile
            length_score * 0.05           # 5% length
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
        """Apply kurtosis-based normalization to scores"""
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
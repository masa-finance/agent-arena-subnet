from abc import ABC, abstractmethod
from typing import Dict
from interfaces.types import Tweet
from validator.config.scoring_config import ScoringWeights

class BaseScoringStrategy(ABC):
    """Abstract base class defining the interface for scoring strategies.
    
    This class provides the foundation for implementing different scoring algorithms
    for social media posts. Each concrete strategy must implement methods for
    calculating individual post scores and normalizing collections of scores.

    Attributes:
        weights (ScoringWeights): Configuration object containing weight parameters
            for different scoring components.
    """

    def __init__(self, weights: ScoringWeights):
        """Initialize the scoring strategy with weight configurations.

        Args:
            weights (ScoringWeights): Configuration object containing scoring weights
                and multipliers for different components of the scoring algorithm.
        """
        self.weights = weights

    @abstractmethod
    def calculate_post_score(self,
                           semantic_score: float,
                           engagement_score: float,
                           profile_score: float,
                           text_length_ratio: float,
                           is_verified: bool) -> float:
        """Calculate individual post score based on component scores.

        Args:
            semantic_score (float): Score representing semantic relevance (0.0-1.0)
            engagement_score (float): Score based on post engagement metrics
            profile_score (float): Score based on user profile strength (0.0-1.0)
            text_length_ratio (float): Ratio of actual to ideal text length
            is_verified (bool): Whether the post author is verified

        Returns:
            float: Calculated composite score for the post
        """
        pass

    @abstractmethod
    def normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Apply score normalization strategy to a collection of scores.

        Args:
            scores (Dict[int, float]): Dictionary mapping post/user IDs to their
                raw calculated scores

        Returns:
            Dict[int, float]: Dictionary of normalized scores maintaining the same
                ID mapping
        """
        pass 
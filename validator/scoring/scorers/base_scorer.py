from abc import ABC, abstractmethod
from typing import Any, Optional
from interfaces.types import Tweet
from validator.config.scoring_config import ScoringWeights

class BaseScorer(ABC):
    """Abstract base class defining the interface for scoring components.
    
    This class serves as the foundation for implementing different scoring components
    that evaluate specific aspects of social media posts. Each concrete scorer must
    implement the calculate_score method to provide its specific scoring logic.

    Attributes:
        weights (ScoringWeights): Configuration object containing weight parameters
            for different scoring aspects. If not provided, default weights are used.
    """
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        """Initialize scorer with weights configuration.

        Args:
            weights (Optional[ScoringWeights], optional): Configuration object containing
                scoring weights and multipliers. If None, default weights are used.
                Defaults to None.
        """
        self.weights = weights or ScoringWeights()
    
    @abstractmethod
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate score for a single post.

        Args:
            post (Tweet): The post object to be scored
            **kwargs: Additional keyword arguments that may be required by specific
                scoring implementations

        Returns:
            float: Calculated score for the given post, typically in range 0.0-1.0
        """
        pass 
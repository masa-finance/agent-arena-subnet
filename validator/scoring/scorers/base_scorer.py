from abc import ABC, abstractmethod
from typing import Any, Optional
from interfaces.types import Tweet
from validator.config.scoring_config import ScoringWeights

class BaseScorer(ABC):
    """Base class for all scoring components"""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        """Initialize scorer with weights configuration"""
        self.weights = weights or ScoringWeights()
    
    @abstractmethod
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate score for a single post"""
        pass 
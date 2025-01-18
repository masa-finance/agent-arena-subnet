from abc import ABC, abstractmethod
from typing import Any
from interfaces.types import Tweet

class BaseScorer(ABC):
    """Base class for all scoring components"""
    
    @abstractmethod
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate score for a single post"""
        pass 
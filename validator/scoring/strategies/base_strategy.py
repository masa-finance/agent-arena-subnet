from abc import ABC, abstractmethod
from typing import Dict
from interfaces.types import Tweet
from validator.config.scoring_config import ScoringWeights

class BaseScoringStrategy(ABC):
    """Abstract base class for scoring strategies"""
    def __init__(self, weights: ScoringWeights):
        self.weights = weights

    @abstractmethod
    def calculate_post_score(self,
                           semantic_score: float,
                           engagement_score: float,
                           profile_score: float,
                           text_length_ratio: float,
                           is_verified: bool) -> float:
        """Calculate individual post score based on component scores"""
        pass

    @abstractmethod
    def normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Apply score normalization strategy"""
        pass 
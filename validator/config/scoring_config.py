from dataclasses import dataclass
from typing import Dict

@dataclass
class ScoringWeights:
    """Configuration for scoring weights"""
    engagement_weights: Dict[str, float] = None
    length_weight: float = 0.25
    semantic_weight: float = 3.0

    def __post_init__(self):
        if self.engagement_weights is None:
            self.engagement_weights = {
                "Likes": 1.0,
                "Retweets": 0.75,
                "Replies": 0.5,
                "Views": 0.05,
            } 
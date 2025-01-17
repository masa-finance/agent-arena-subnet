from dataclasses import dataclass
from typing import Dict

@dataclass
class ScoringWeights:
    """Configuration for scoring weights"""
    engagement_weights: Dict[str, float] = None
    length_weight: float = 0.1
    semantic_weight: float = 0.6

    def __post_init__(self):
        if self.engagement_weights is None:
            self.engagement_weights = {
                "Likes": 0.3,
                "Retweets": 0.2,
                "Replies": 0.4,
                "Views": 0.1,
            } 
from dataclasses import dataclass
import numpy as np

@dataclass
class AggregateWeights:
    """
    Configuration for combining different scoring components.
    Controls how different scoring aspects (semantic, engagement, etc.) 
    are weighted in the final score calculation.
    """
    semantic_weight: float = 0.6     # Weight for semantic scoring component
    engagement_weight: float = 0.4   # Weight for engagement scoring component

    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = self.semantic_weight + self.engagement_weight
        if not np.isclose(total, 1.0):
            raise ValueError(f"Aggregate weights must sum to 1.0, got {total}")

    def get_weights(self) -> dict:
        """Return weights as a dictionary"""
        return {
            'semantic': self.semantic_weight,
            'engagement': self.engagement_weight
        } 
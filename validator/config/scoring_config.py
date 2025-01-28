from dataclasses import dataclass
from typing import Dict

@dataclass
class ScoringWeights:
    """
    Comprehensive configuration for the scoring system.
    Centralizes all weights, ratios, and thresholds used across different scorers.
    """
    # === Base Component Ratios ===
    semantic_ratio: float = 0.7     # 70% semantic analysis
    engagement_ratio: float = 0.15  # 15% engagement
    profile_ratio: float = 0.1      # 10% profile features
    length_ratio: float = 0.05      # 5% text length

    # === Semantic Scoring ===
    semantic_weight: float = 0.6
    semantic_multiplier: float = 2.0
    semantic_config: Dict[str, float] = None  # Will be set in post_init
    
    # === Engagement Scoring ===
    engagement_weights: Dict[str, float] = None  # Will be set in post_init
    engagement_multiplier: float = 0.5
    healthy_reply_ratio_min: float = 0.1   # Min ratio for healthy replies/likes
    healthy_reply_ratio_max: float = 2.0   # Max ratio for healthy replies/likes
    healthy_conversation_bonus: float = 1.2  # Bonus multiplier for healthy conversations
    
    # === Profile Scoring ===
    profile_weights: Dict[str, float] = None  # Will be set in post_init
    followers_cap: float = 11.5  # ln(100000) - cap at 100k followers
    followers_dampening: float = 0.6  # Dampening factor for followers
    
    # === Length Scoring ===
    length_weight: float = 0.1
    max_length: int = 280  # Maximum post length

    def __post_init__(self):
        """Initialize default configurations"""
        # Set default semantic config
        if self.semantic_config is None:
            self.semantic_config = {
                'originality': 0.7,
                'uniqueness': 0.3,
                'similarity_threshold': 0.85,
                'keyword_threshold': 0.3,
                'min_post_length': 20
            }

        # Set default engagement weights
        if self.engagement_weights is None:
            self.engagement_weights = {
                "Replies": 0.4,
                "Likes": 0.3,
                "Retweets": 0.2,
                "Views": 0.1
            }

        # Set default profile weights
        if self.profile_weights is None:
            self.profile_weights = {
                "followers_weight": 0.6,
                "verified_weight": 0.4
            }

        self._validate_weights()

    def _validate_weights(self):
        """Validate all weights and ratios"""
        # Validate base ratios sum to 1.0
        total_ratio = (self.semantic_ratio + self.engagement_ratio + 
                      self.profile_ratio + self.length_ratio)
        if not abs(total_ratio - 1.0) < 1e-10:
            raise ValueError(f"Score ratios must sum to 1.0, got {total_ratio}")

        # Validate engagement weights sum to 1.0
        total_engagement = sum(self.engagement_weights.values())
        if not abs(total_engagement - 1.0) < 1e-10:
            raise ValueError(f"Engagement weights must sum to 1.0, got {total_engagement}")

        # Validate semantic weights sum to 1.0
        total_semantic = sum(
            v for k, v in self.semantic_config.items() 
            if k in ['originality', 'uniqueness']
        )
        if not abs(total_semantic - 1.0) < 1e-10:
            raise ValueError(f"Semantic weights must sum to 1.0, got {total_semantic}")

        # Validate profile weights sum to 1.0
        total_profile = sum(self.profile_weights.values())
        if not abs(total_profile - 1.0) < 1e-10:
            raise ValueError(f"Profile weights must sum to 1.0, got {total_profile}") 
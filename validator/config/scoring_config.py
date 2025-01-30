from dataclasses import dataclass, field
from typing import Dict, Tuple

@dataclass
class VerificationConfig:
    """Configuration for verification-based scoring adjustments"""
    minimum_score: float = 0.5      # Minimum score for verified accounts
    unverified_ratio: float = 2.0   # Verified scores must be at least 2x unverified
    unverified_cap: float = 0.5     # Unverified scores capped at 50% of min verified

@dataclass
class ScoringWeights:
    """
    Comprehensive configuration for the scoring system.
    Centralizes all weights, ratios, and thresholds used across different scorers.
    """
    # === Base Component Ratios ===
    semantic_ratio: float = 0.7     
    engagement_ratio: float = 0.15  
    follower_ratio: float = 0.05    # Split profile ratio between followers/verification
    verification_ratio: float = 0.05 
    length_ratio: float = 0.05      

    # === Semantic Scoring ===
    semantic_weight: float = 0.6
    semantic_multiplier: float = 2.0
    semantic_config: Dict[str, float] = field(default_factory=lambda: None)
    
    # === Engagement Scoring ===
    engagement_weights: Dict[str, float] = field(default_factory=lambda: None)
    engagement_multiplier: float = 0.5
    healthy_reply_ratio_min: float = 0.1   # Min ratio for healthy replies/likes
    healthy_reply_ratio_max: float = 2.0   # Max ratio for healthy replies/likes
    healthy_conversation_bonus: float = 1.2  # Bonus multiplier for healthy conversations
    
    # === Follower Scoring ===
    followers_cap: float = 11.5  # ln(100000) - cap at 100k followers
    followers_dampening: float = 0.6  # Dampening factor for followers
    
    # === Length Scoring ===
    length_weight: float = 0.1
    max_length: int = 280  # Maximum post length

    # === Verification Config ===
    verification: VerificationConfig = field(default_factory=VerificationConfig)

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
                "Retweets": 0.4,    # Most impactful - shows active content sharing
                "Replies": 0.3,     # Second most - shows active engagement/discussion
                "Likes": 0.2,       # Third - shows passive positive engagement
                "Views": 0.1        # Least - shows reach but lowest engagement level
            }

        # Validate base ratios sum to 1.0
        total_ratio = (self.semantic_ratio + self.engagement_ratio + 
                      self.follower_ratio + self.verification_ratio + 
                      self.length_ratio)
        if not abs(total_ratio - 1.0) < 1e-10:
            raise ValueError(f"Score ratios must sum to 1.0, got {total_ratio}")

    def _validate_weights(self):
        """Validate all weights and ratios"""
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

    def scale_verification_scores(self, 
                                verified_scores: Dict[int, float], 
                                unverified_scores: Dict[int, float]) -> Tuple[Dict[int, float], Dict[int, float]]:
        """
        Scale scores to ensure verified accounts always score higher than unverified.
        """
        if not verified_scores:
            return verified_scores, unverified_scores

        # Ensure verified scores meet minimum threshold
        min_verified = max(min(verified_scores.values()), self.verification.minimum_score)
        verified_scores = {
            uid: max(score, self.verification.minimum_score) 
            for uid, score in verified_scores.items()
        }

        # Scale unverified scores to be below minimum verified
        if unverified_scores:
            max_unverified = max(unverified_scores.values())
            if max_unverified > 0:
                target_max = min_verified * self.verification.unverified_cap
                scale_factor = target_max / max_unverified
                unverified_scores = {
                    uid: score * scale_factor 
                    for uid, score in unverified_scores.items()
                }

        return verified_scores, unverified_scores 
from typing import Optional, Set
import numpy as np
from interfaces.types import Tweet, RegisteredAgentResponse
from .base_scorer import BaseScorer
import logging

logger = logging.getLogger(__name__)

class FollowerConfig:
    """Configuration for follower scoring parameters"""
    MIN_FOLLOWERS = 100  # Minimum followers for base score
    MAX_FOLLOWERS = 100000  # Cap for follower count scaling
    VERIFIED_BONUS = 0.1  # Bonus score for verified accounts

class FollowerScorer(BaseScorer):
    """Analyzes follower metrics to calculate influence scores."""
    
    def __init__(self):
        self.config = FollowerConfig()
        self._logged_missing_agents: Set[str] = set()
        self._logged_agents: Set[str] = set()
    
    def calculate_score(self, post: Tweet, agent: Optional[RegisteredAgentResponse] = None) -> float:
        """Calculate follower-based score for a single post"""
        # Get UserID from dict
        user_id = str(post.get("UserID", ""))
        
        if not agent:
            # Only log missing agent once
            if user_id not in self._logged_missing_agents:
                self._logged_missing_agents.add(user_id)
                logger.warning(f"No agent found for UserID: {user_id}")
            return 0.0
            
        # Get follower count with bounds
        followers = min(
            max(agent.FollowersCount, self.config.MIN_FOLLOWERS),
            self.config.MAX_FOLLOWERS
        )
        
        # Calculate base score using log scaling
        base_score = np.log1p(followers / self.config.MIN_FOLLOWERS) / np.log1p(
            self.config.MAX_FOLLOWERS / self.config.MIN_FOLLOWERS
        )
        
        # Apply verified bonus if applicable
        if agent.IsVerified:
            base_score *= (1 + self.config.VERIFIED_BONUS)
            final_score = float(np.clip(base_score, 0, 1))
            # Only log once per agent
            if agent.Username not in self._logged_agents:
                self._logged_agents.add(agent.Username)
                logger.debug(f"Agent {agent.Username} (Verified): Followers={followers:,}, Score={final_score:.4f}")
        else:
            final_score = float(np.clip(base_score, 0, 1))
            # Only log once per agent
            if agent.Username not in self._logged_agents:
                self._logged_agents.add(agent.Username)
                logger.debug(f"Agent {agent.Username}: Followers={followers:,}, Score={final_score:.4f}")
            
        return final_score 
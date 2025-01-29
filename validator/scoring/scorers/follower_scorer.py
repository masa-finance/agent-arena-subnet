"""Follower Count Scoring Module

This module provides functionality for scoring social media posts based on the author's 
follower count. It implements a logarithmic scaling approach to normalize follower counts
into scores between 0.0 and 1.0.

The scoring mechanism works as follows:
1. Determines the maximum follower count from the entire dataset during initialization
2. Uses logarithmic scaling (log1p) to handle the wide range of follower counts
3. Normalizes scores relative to the maximum follower count
4. Supports a configurable minimum follower threshold

Example:
    scorer = FollowerScorer(weights={'min_followers': 100})
    scorer.initialize_scorer(posts)
    score = scorer.calculate_score(post)

Attributes:
    logger: Module-level logger instance
"""

from typing import Any, List
import numpy as np
from validator.scoring.scorers.base_scorer import BaseScorer
from interfaces.types import Tweet
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

class FollowerScorer(BaseScorer):
    """Evaluates profiles based on follower metrics.
    
    This scorer determines the maximum follower count from the entire dataset
    and uses it to normalize scores between 0.0 and 1.0 using log scaling.
    
    Config parameters:
        min_followers: Minimum followers required for non-zero score (default: 0)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_followers = None
        self._followers_cap = None
        
    def initialize_scorer(self, posts: List[Tweet]) -> None:
        """Initialize scorer with the complete dataset to establish max followers.
        
        Args:
            posts: List of all posts to be scored
        """
        try:
            all_followers = [post.get("FollowersCount", 0) for post in posts]
            self._max_followers = max(all_followers)
            self._followers_cap = np.log1p(self._max_followers)
            logger.info(f"Initialized FollowerScorer with max followers: {self._max_followers}")
        except Exception as e:
            logger.error(f"Error initializing follower scorer: {str(e)}")
            self._max_followers = 0
            self._followers_cap = 0
            
    def calculate_score(self, post: Tweet, **kwargs: Any) -> float:
        """Calculate normalized follower score.

        Args:
            post (Tweet): Post object containing author profile information
            **kwargs: Additional arguments (unused)

        Returns:
            float: Normalized follower score between 0.0 and 1.0
        """
        if self._followers_cap is None:
            logger.warning("FollowerScorer not initialized. Call initialize_scorer first.")
            return 0.0
            
        try:
            followers_count = post.get("FollowersCount", 0)
            
            if not self._has_valid_followers(followers_count):
                return 0.0
                
            return self._compute_normalized_score(followers_count)
            
        except Exception as e:
            logger.error(f"Error calculating follower score: {str(e)}")
            return 0.0
            
    def _has_valid_followers(self, count: int) -> bool:
        """Check if follower count meets minimum threshold."""
        min_followers = getattr(self.weights, 'min_followers', 0)
        return count >= min_followers
        
    def _compute_normalized_score(self, followers_count: int) -> float:
        """Compute normalized score using log scaling relative to max followers."""
        if self._followers_cap == 0:
            return 0.0
            
        log_followers = np.log1p(followers_count)
        return min(1.0, log_followers / self._followers_cap) 
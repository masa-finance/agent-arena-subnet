from typing import Dict, List
from interfaces.types import Tweet
from validator.scoring.scorers.base_scorer import BaseScorer
import numpy as np
from fiber.logging_utils import get_logger
import logging

logger = get_logger(__name__)

class EngagementScorer(BaseScorer):
    """Calculates engagement scores based on configured weights and metrics.
    
    This scorer evaluates post engagement using weights defined in scoring_config.py.
    
    Engagement metrics and their default weights (from scoring_config.py):
    - Retweets (0.4): 40% of engagement score - Most impactful, shows active content sharing
    - Replies (0.3): 30% of engagement score - Active discussion and engagement
    - Likes (0.2): 20% of engagement score - Passive positive engagement
    - Views (0.1): 10% of engagement score - Basic reach metric

    The scoring process:
    1. Applies logarithmic scaling (np.log1p) to raw engagement numbers
    2. Normalizes each metric relative to the maximum value in the dataset
    3. Applies configured weights to normalized values
    4. Returns a final score between 0.0 and 1.0
    """

    def __init__(self, *args, **kwargs):
        """Initialize the EngagementScorer with empty maximum metrics dictionary."""
        super().__init__(*args, **kwargs)
        self._max_metrics = {}
        
    def initialize_scorer(self, posts: List[Tweet]) -> None:
        """Initialize scorer with maximum values for each metric.
        
        Processes the entire dataset to find the maximum value for each
        engagement metric (Retweets, Replies, Likes, Views). These maximums
        are used to normalize individual post scores.
        
        Args:
            posts: List of all posts to be scored
        """
        try:
            # Find max value for each engagement metric
            for metric in self.weights.engagement_weights.keys():
                values = [post.get(metric, 0) for post in posts]
                self._max_metrics[metric] = max(values) if values else 0
                logger.info(f"Initialized max {metric}: {self._max_metrics[metric]}")
        except Exception as e:
            logger.error(f"Error initializing engagement scorer: {str(e)}")
            self._max_metrics = {}

    def calculate_score(self, post: Tweet) -> float:
        """Calculate normalized engagement score for a single post.
        
        The score is calculated by:
        1. For each metric (Retweets, Replies, Likes, Views):
           - Normalize the value using log1p relative to max value
           - Multiply by the metric's weight
        2. Sum all weighted normalized values
        3. Return final score between 0.0 and 1.0
        
        Example:
            Post with: Retweets=10, Replies=20, Likes=50, Views=1000
            Max values: Retweets=45, Replies=433, Likes=261, Views=64440
            
            Calculations:
            Retweets: (log1p(10)/log1p(45)) * 0.4 = 0.731 * 0.4 = 0.292
            Replies: (log1p(20)/log1p(433)) * 0.3 = 0.511 * 0.3 = 0.153
            Likes: (log1p(50)/log1p(261)) * 0.2 = 0.674 * 0.2 = 0.135
            Views: (log1p(1000)/log1p(64440)) * 0.1 = 0.556 * 0.1 = 0.056
            
            Final Score = 0.636 (sum of all components)
        """
        if not self._validate_initialization():
            return 0.0

        try:
            total_score = 0.0
            
            for metric, weight in self.weights.engagement_weights.items():
                value = float(post.get(metric, 0))
                max_value = float(self._max_metrics.get(metric, 1))  # Avoid div by zero
                
                if value > 0 and max_value > 0:
                    # Log transform and normalize
                    normalized = np.log1p(value) / np.log1p(max_value)
                    weighted = normalized * weight
                    total_score += weighted
                    
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"{metric}: {value}/{max_value} -> {normalized:.3f} * {weight} = {weighted:.3f}")

            return min(1.0, max(0.0, total_score))
            
        except Exception as e:
            logger.error(f"Error calculating score: {str(e)}")
            return 0.0

    def _validate_initialization(self) -> bool:
        """Validate that the scorer has been properly initialized.

        Returns:
            bool: True if all required maximum metrics are present, False otherwise
        """
        return (bool(self._max_metrics) and 
                all(metric in self._max_metrics 
                    for metric in self.weights.engagement_weights))

    def calculate_scores(self, posts: List[Tweet]) -> Dict[str, float]:
        """Calculate normalized engagement scores for multiple posts.
        
        Note: initialize_scorer must be called first with the complete dataset
        to establish maximum values for normalization.

        Args:
            posts: List of posts to score

        Returns:
            Dict mapping post IDs to their normalized engagement scores (0.0-1.0)
        """
        if not self._validate_initialization():
            logger.warning("EngagementScorer not initialized. Call initialize_scorer first.")
            return {}

        try:
            return {
                post.get('id'): self.calculate_score(post)
                for post in posts
            }
        except Exception as e:
            logger.error(f"Error calculating bulk engagement scores: {str(e)}")
            return {} 
from typing import Dict, List
from interfaces.types import Tweet
from validator.scoring.scorers.base_scorer import BaseScorer
import numpy as np
from fiber.logging_utils import get_logger

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
        """Calculate normalized engagement score using weights from scoring_config.py.

        The score is computed by:
        1. Getting each metric's value from the post
        2. Applying logarithmic transformation (np.log1p)
        3. Normalizing against the maximum value for that metric
        4. Multiplying by the corresponding weight
        5. Summing all weighted values

        Args:
            post (Tweet): The post object containing engagement metrics:
                - Retweets: Number of times the post was shared
                - Replies: Number of responses to the post
                - Likes: Number of likes/favorites
                - Views: Number of times the post was viewed

        Returns:
            float: The normalized engagement score between 0.0 and 1.0
                  A score of 1.0 indicates maximum engagement across all metrics
                  A score of 0.0 indicates no engagement
        """
        if not self._max_metrics:
            logger.warning("EngagementScorer not initialized. Call initialize_scorer first.")
            return 0.0

        try:
            score = 0
            
            # Calculate weighted engagement metrics
            for metric, weight in self.weights.engagement_weights.items():
                value = post.get(metric, 0)
                if value > 0 and self._max_metrics[metric] > 0:
                    # Normalize using log transformation
                    normalized_value = (np.log1p(value) / 
                                     np.log1p(self._max_metrics[metric]))
                    score += normalized_value * weight
                
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating engagement score: {str(e)}")
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
from typing import Dict, List, Any
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, UTC, timedelta
from interfaces.types import Tweet
from fiber.logging_utils import get_logger
from .semantic_scorer import SemanticScorer
from tqdm import tqdm

logger = get_logger(__name__)


class PostsScorer:
    def __init__(self, validator: Any):
        self.engagement_weights = {
            "Likes": 1.0,
            "Retweets": 0.75,
            "Replies": 0.5,
            "Views": 0.05,
        }
        self.length_weight = 0.25
        self.semantic_weight = 3.0
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.validator = validator
        self.semantic_scorer = SemanticScorer()

    def _calculate_post_score(self, post: Tweet, semantic_score: float) -> float:
        tweet_data = dict(post)
        base_score = 0

        # Calculate text length score
        text = tweet_data.get("Text", "")
        text_length = len(str(text))
        base_score += text_length * self.length_weight

        # Calculate engagement score
        for metric, weight in self.engagement_weights.items():
            value = tweet_data.get(metric, 0)
            base_score += value * weight

        # Add semantic score
        base_score += semantic_score * self.semantic_weight

        return np.log1p(base_score)

    def calculate_agent_scores(self, posts: List[Tweet]) -> Dict[int, float]:
        if not posts:
            logger.warning("No posts provided for scoring")
            return {}
            
        logger.info("Starting scoring process...")
        
        # Filter posts from the last 7 days
        current_time = datetime.now(UTC)
        scoring_window = timedelta(days=7)
        
        filtered_posts = [
            post for post in posts 
            if (current_time - datetime.fromtimestamp(post.get("Timestamp", 0), UTC)) <= scoring_window
        ]
            
        logger.info("Input posts breakdown:")
        logger.info("- Total posts: %d", len(posts))
        logger.info("- Posts in 7d window: %d", len(filtered_posts))
        logger.info("- Unique users: %d", len(set(post.get("UserID") for post in filtered_posts)))
        logger.info("- Posts with text: %d", len([p for p in filtered_posts if p.get("Text")]))
        
        # Create a temporary dictionary mapping UserId to UID
        user_id_to_uid = {
            agent.UserID: int(agent.UID)
            for agent in self.validator.registered_agents.values()
        }
        
        # Initialize scores dict with zeros for all registered agents
        final_scores = {uid: 0.0 for uid in user_id_to_uid.values()}

        # Group posts by UID first
        posts_by_uid: Dict[int, List[Tweet]] = {}
        for post in filtered_posts:
            user_id = post.get("UserID")
            if not user_id or user_id not in user_id_to_uid:
                continue
            uid = user_id_to_uid[user_id]
            if uid not in posts_by_uid:
                posts_by_uid[uid] = []
            posts_by_uid[uid].append(post)

        # Single progress bar for all agents
        with tqdm(total=len(posts_by_uid), desc="Scoring all agents", unit="agent") as pbar:
            for uid, agent_posts in posts_by_uid.items():
                if not agent_posts:
                    continue
                    
                post_texts = [post.get("Text", "") for post in agent_posts]
                if not any(post_texts):
                    continue
                    
                semantic_scores = self.semantic_scorer.calculate_scores(post_texts)
                semantic_scores = np.nan_to_num(semantic_scores, nan=0.0, posinf=100.0, neginf=0.0)
                
                scores = []
                for idx, post in enumerate(agent_posts):
                    try:
                        score = self._calculate_post_score(post, semantic_scores[idx])
                        if np.isfinite(score):
                            scores.append(score)
                    except Exception as e:
                        logger.warning(f"Error processing post for UID {uid}: {str(e)}")
                        continue
                
                if scores:
                    mean_score = np.mean(scores)
                    post_count = len(scores)
                    final_scores[uid] = mean_score * np.log1p(post_count)
                
                pbar.update(1)
        
        # Handle any remaining inf values before normalization
        scores_array = np.array(list(final_scores.values())).reshape(-1, 1)
        scores_array = np.nan_to_num(scores_array, nan=0.0, posinf=100.0, neginf=0.0)
        
        # Only normalize if we have non-zero finite scores
        non_zero_scores = [score for score in scores_array.flatten() if score > 0]
        if len(non_zero_scores) > 1:
            try:
                normalized_scores = self.scaler.fit_transform(scores_array).flatten()
                final_scores = {
                    uid: score for uid, score in zip(final_scores.keys(), normalized_scores)
                }
            except Exception as e:
                logger.error(f"Error during score normalization: {str(e)}")
                # If normalization fails, return the non-normalized scores
                final_scores = {
                    uid: score for uid, score in zip(final_scores.keys(), scores_array.flatten())
                }
            
        logger.info("Scoring complete:")
        logger.info("- Total agents scored: %d", len(final_scores))
        logger.info("- Agents with non-zero scores: %d", len(non_zero_scores))
        
        return final_scores

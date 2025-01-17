from typing import Dict, List, Any
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, UTC
from interfaces.types import Tweet
from fiber.logging_utils import get_logger
from .semantic_scorer import SemanticScorer

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
        current_time = datetime.now(UTC)
        
        logger.debug("Starting scoring for %d posts", len(posts))
        
        # Get semantic scores for all posts
        post_texts = [post.get("Text", "") for post in posts]
        semantic_scores = self.semantic_scorer.calculate_scores(post_texts)
        logger.debug("Generated semantic scores: %d scores", len(semantic_scores))

        agent_posts: Dict[int, List[float]] = {}
        skipped_posts = 0
        processed_posts = 0

        # Create a temporary dictionary mapping UserId to UID
        user_id_to_uid = {
            agent.UserID: int(agent.UID)
            for agent in self.validator.registered_agents.values()
        }
        logger.debug("Found %d registered agents", len(user_id_to_uid))

        for idx, post in enumerate(posts):
            try:
                user_id = post.get("UserID", None)
                if not user_id:
                    logger.debug("Post %d: Missing UserID", idx)
                    skipped_posts += 1
                    continue

                uid = user_id_to_uid.get(user_id, None)
                if not uid:
                    logger.debug("Post %d: UserID %s not found in registered agents", idx, user_id)
                    skipped_posts += 1
                    continue

                try:
                    score = self._calculate_post_score(post, semantic_scores[idx])
                    logger.debug("Post %d: UID %d, semantic_score=%.3f, final_score=%.3f", 
                                idx, uid, semantic_scores[idx], score)
                    
                    if uid not in agent_posts:
                        agent_posts[uid] = []
                    agent_posts[uid].append(score)
                    processed_posts += 1

                except Exception as e:
                    logger.warning("Error processing post %d: %s", idx, str(e))
                    skipped_posts += 1
                    continue

            except Exception as e:
                logger.warning("Error in post loop at index %d: %s", idx, str(e))
                skipped_posts += 1
                continue

        logger.info("Processed %d posts, skipped %d", processed_posts, skipped_posts)
        logger.info("Found posts for %d unique agents", len(agent_posts))

        # Calculate final scores
        final_scores = {}
        for uid, scores in agent_posts.items():
            if scores:
                mean_score = np.mean(scores)
                post_count = len(scores)
                final_score = mean_score * np.log1p(post_count)
                final_scores[uid] = final_score
                logger.debug("Agent %d: posts=%d, mean_score=%.3f, final_score=%.3f", 
                             uid, post_count, mean_score, final_score)

        if final_scores:
            scores_array = np.array(list(final_scores.values())).reshape(-1, 1)
            normalized_scores = self.scaler.fit_transform(scores_array).flatten()
            final_scores = {
                uid: score for uid, score in zip(final_scores.keys(), normalized_scores)
            }
            logger.debug("Normalized score ranges: min=%.3f, max=%.3f", 
                         np.min(normalized_scores), np.max(normalized_scores))

        return final_scores

from typing import Dict, List, Any
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, UTC
from interfaces.types import Tweet
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


class PostsScorer:
    def __init__(self, validator: Any):
        self.engagement_weights = {
            "Likes": 2.0,
            "Retweets": 1.5,
            "Replies": 1.0,
            "Views": 0.1,
        }
        self.length_weight = 0.5
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.validator = validator

    def _calculate_post_score(self, post: Tweet) -> float:
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

        return np.log1p(base_score)

    def calculate_agent_scores(self, posts: List[Tweet]) -> Dict[int, float]:
        current_time = datetime.now(UTC)

        agent_posts: Dict[int, List[float]] = {}
        skipped_posts = 0
        processed_posts = 0

        # Create a temporary dictionary mapping UserId to UID
        user_id_to_uid = {
            agent.UserID: int(agent.UID)
            for agent in self.validator.registered_agents.values()
        }

        for post in posts:
            try:
                user_id = post.get("UserID", None)
                if not user_id:
                    logger.info(f"Post does not have a UserID...")
                    skipped_posts += 1
                    continue

                uid = user_id_to_uid.get(user_id, None)
                if uid is None:
                    skipped_posts += 1
                    continue

                try:
                    timestamp = post.get("Timestamp")
                    if timestamp:
                        timestamp = datetime.fromtimestamp(timestamp, UTC)
                    else:
                        timestamp = current_time

                    if uid not in agent_posts:
                        agent_posts[uid] = []

                    score = self._calculate_post_score(post)
                    agent_posts[uid].append(score)
                    processed_posts += 1

                except Exception as e:
                    skipped_posts += 1
                    continue

            except Exception as e:
                skipped_posts += 1
                continue

        logger.info(f"Processed {processed_posts} posts, skipped {skipped_posts}")
        logger.info(f"Found posts for {len(agent_posts)} unique agents")

        final_scores = {}
        for uid, scores in agent_posts.items():
            if scores:
                mean_score = np.mean(scores)
                post_count = len(scores)
                final_score = mean_score * np.log1p(post_count)
                final_scores[uid] = final_score

        # logger.info(f"Final Scores Before Normalization: {final_scores}")

        if final_scores:
            scores_array = np.array(list(final_scores.values())).reshape(-1, 1)
            normalized_scores = self.scaler.fit_transform(scores_array).flatten()
            final_scores = {
                uid: score for uid, score in zip(final_scores.keys(), normalized_scores)
            }

        # logger.info(f"Final Scores After Normalization: {final_scores}")
        return final_scores

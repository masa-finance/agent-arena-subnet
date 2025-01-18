from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, UTC, timedelta
from tqdm import tqdm
from interfaces.types import Tweet
from fiber.logging_utils import get_logger
from validator.config.hardware_config import HardwareConfig, PerformanceConfig
from validator.config.scoring_config import ScoringWeights
from validator.config.progress_config import ProgressBarConfig, ProgressStages, ScoringProgressConfig, ShapProgressConfig
from validator.scorers.semantic_scorer import SemanticScorer
from validator.scorers.engagement_scorer import EngagementScorer
from validator.scorers.feature_importance import FeatureImportanceCalculator
from time import time
from validator.scorers.follower_scorer import FollowerScorer

logger = get_logger(__name__)

class AgentScorer:
    """
    New implementation of the scoring system with improved modularity.
    This will gradually replace PostsScorer.
    """
    def __init__(self, 
                 validator: Any, 
                 scoring_hardware_config: Optional[HardwareConfig] = None,
                 shap_hardware_config: Optional[HardwareConfig] = None):
        # Initialize configurations
        self.scoring_config = scoring_hardware_config or PerformanceConfig.get_config()
        self.shap_config = shap_hardware_config or self.scoring_config
        self.weights = ScoringWeights()
        
        # Initialize components
        self.validator = validator
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.semantic_scorer = SemanticScorer(self.scoring_config)
        self.engagement_scorer = EngagementScorer(self.weights)
        self.feature_calculator = FeatureImportanceCalculator(
            config=self.shap_config,
            weights=self.weights,
            semantic_scorer=self.semantic_scorer,
            validator=self.validator
        )
        self.follower_scorer = FollowerScorer()
        
        self._log_initialization()

    def _log_initialization(self) -> None:
        """Log initialization details"""
        logger.info(f"Initialized AgentScorer with scoring hardware config: {self.scoring_config}")
        logger.info(f"Using scoring device type: {self.scoring_config.device_type}")
        if self.scoring_config.gpu_memory:
            logger.info(f"Scoring GPU Memory: {self.scoring_config.gpu_memory}GB")
            
        logger.info(f"Using SHAP hardware config: {self.shap_config}")
        logger.info(f"Using SHAP device type: {self.shap_config.device_type}")
        if self.shap_config.gpu_memory:
            logger.info(f"SHAP GPU Memory: {self.shap_config.gpu_memory}GB")

    def _calculate_post_score(self, post: Tweet, semantic_score: float) -> float:
        """Calculate individual post score with semantic quality and follower metrics"""
        text = post.get("Text", "")
        
        # Get the agent data for follower scoring - use str(UserID) for lookup
        user_id = str(post.get("UserID"))
        agent = self.validator.registered_agents.get(user_id)
        follower_score = self.follower_scorer.calculate_score(post, agent)
        
        # Calculate other scores as before
        text_length = min(len(str(text)), 280) / 280
        length_score = text_length * (self.weights.length_weight * 0.1)
        engagement_score = min(self.engagement_scorer.calculate_score(post), 1.0)
        weighted_semantic = semantic_score * (self.weights.semantic_weight * 2.0)
        
        # Combine scores with follower influence
        base_score = (
            weighted_semantic * 0.55 +     # 55% semantic
            engagement_score * 0.15 +      # 15% engagement
            follower_score * 0.25 +        # 25% follower influence
            length_score * 0.05            # 5% length
        )
        
        # Apply quality multiplier
        quality_multiplier = 1.0 + (semantic_score * 0.5)
        
        return np.log1p(base_score * quality_multiplier)

    def calculate_scores(self, posts: List[Tweet]) -> Tuple[Dict[int, float], Dict[str, float]]:
        """
        Calculate agent scores from posts.
        Returns:
            Tuple[Dict[int, float], Dict[str, float]]: (agent_scores, feature_importance)
        """
        if not posts:
            logger.warning("No posts provided for scoring")
            return {}, {}
            
        try:
            # Step 1: Filter posts
            filtered_posts = self._filter_recent_posts(posts)
            stats = self._calculate_post_stats(filtered_posts)
            
            # Step 2: Process posts by agent
            posts_by_uid = self._group_posts_by_agent(filtered_posts)
            
            progress_config = ScoringProgressConfig(total_agents=len(posts_by_uid))
            
            with progress_config.create_progress_bar() as main_pbar:
                main_pbar.set_postfix(**stats)
                
                # Step 3: Calculate scores
                agent_scores = self._calculate_agent_scores(posts_by_uid, main_pbar)
                
                # Step 4: Calculate feature importance with ShapProgressConfig
                shap_config = ShapProgressConfig(total_samples=self.shap_config.shap_background_samples)
                with shap_config.create_progress_bar() as shap_pbar:
                    feature_importance = self.feature_calculator.calculate(
                        filtered_posts, 
                        progress_bar=shap_pbar
                    )
                    return agent_scores, feature_importance
            
        except Exception as e:
            logger.error(f"Error in calculate_scores: {str(e)}")
            raise

    def _filter_recent_posts(self, posts: List[Tweet]) -> List[Tweet]:
        """Filter posts from the last 7 days"""
        current_time = datetime.now(UTC)
        scoring_window = timedelta(days=7)
        return [
            post for post in posts 
            if (current_time - datetime.fromtimestamp(post.get("Timestamp", 0), UTC)) <= scoring_window
        ]

    def _calculate_post_stats(self, posts: List[Tweet]) -> Dict[str, int]:
        """Calculate post statistics"""
        return {
            "total_posts": len(posts),
            "unique_users": len(set(post.get("UserID") for post in posts)),
            "posts_with_text": len([p for p in posts if p.get("Text")])
        }

    def _group_posts_by_agent(self, posts: List[Tweet]) -> Dict[int, List[Tweet]]:
        """Group posts by agent UID"""
        # Debug logging to see what agents we have
        logger.info(f"Number of registered agents: {len(self.validator.registered_agents)}")
        logger.info("Registered agent UserIDs: %s", [
            agent.UserID for agent in self.validator.registered_agents.values()
        ])
        
        user_id_to_uid = {
            agent.UserID: int(agent.UID)
            for agent in self.validator.registered_agents.values()
        }
        
        # Debug logging for posts
        unmatched_user_ids = set()
        for post in posts:
            user_id = post.get("UserID")
            if user_id and user_id not in user_id_to_uid:
                unmatched_user_ids.add(user_id)
        
        if unmatched_user_ids:
            logger.warning("Found posts from unregistered UserIDs: %s", unmatched_user_ids)
        
        posts_by_uid: Dict[int, List[Tweet]] = {}
        for post in posts:
            user_id = post.get("UserID")
            if not user_id or user_id not in user_id_to_uid:
                continue
            uid = user_id_to_uid[user_id]
            if uid not in posts_by_uid:
                posts_by_uid[uid] = []
            posts_by_uid[uid].append(post)
            
        return posts_by_uid

    def _calculate_agent_scores(self, 
                              posts_by_uid: Dict[int, List[Tweet]], 
                              progress_bar: tqdm) -> Dict[int, float]:
        """Calculate final scores for each agent"""
        final_scores = {uid: 0.0 for uid in posts_by_uid.keys()}
        start_time = time()
        processed_agents = 0
        
        for uid, agent_posts in posts_by_uid.items():
            texts = [post.get("Text", "") for post in agent_posts]
            semantic_scores = self.semantic_scorer.calculate_scores(texts)
            
            scores = []
            for post, semantic_score in zip(agent_posts, semantic_scores):
                try:
                    score = self._calculate_post_score(post, semantic_score)
                    if np.isfinite(score):
                        scores.append(score)
                except Exception as e:
                    logger.warning(f"Error processing post for UID {uid}: {str(e)}")
                    continue

            if scores:
                mean_score = np.mean(scores)
                post_count = len(scores)
                final_scores[uid] = mean_score * np.log1p(post_count)
            
            # Update progress
            processed_agents += 1
            elapsed_time = time() - start_time
            rate = processed_agents / elapsed_time if elapsed_time > 0 else 0
            
            progress_bar.update(1)
            progress_bar.set_postfix({
                "agents": f"{processed_agents}/{len(posts_by_uid)}",
                "rate": f"{rate:.2f} agents/s"
            })

        return self._normalize_scores(final_scores)

    def _normalize_scores(self, scores: Dict[int, float]) -> Dict[int, float]:
        """Normalize agent scores"""
        scores_array = np.array(list(scores.values())).reshape(-1, 1)
        scores_array = np.nan_to_num(scores_array, nan=0.0, posinf=100.0, neginf=0.0)
        
        non_zero_scores = [score for score in scores_array.flatten() if score > 0]
        if len(non_zero_scores) > 1:
            try:
                normalized_scores = self.scaler.fit_transform(scores_array).flatten()
                return {uid: score for uid, score in zip(scores.keys(), normalized_scores)}
            except Exception as e:
                logger.error(f"Error during score normalization: {str(e)}")
        
        return scores


# For backward compatibility
class PostsScorer(AgentScorer):
    """
    Legacy class maintained for backward compatibility.
    Inherits from AgentScorer but keeps the old name.
    """
    def calculate_agent_scores(self, posts: List[Tweet]) -> Tuple[Dict[int, float], Dict[str, float]]:
        """Maintain old method name for compatibility"""
        return self.calculate_scores(posts)
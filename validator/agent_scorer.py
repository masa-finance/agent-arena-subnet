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
from validator.scorers.profile_scorer import ProfileScorer
from time import time
from validator.strategies.base_strategy import BaseScoringStrategy
from validator.strategies.default_strategy import DefaultScoringStrategy

logger = get_logger(__name__)

class AgentScorer:
    """
    New implementation of the scoring system with improved modularity.
    This will gradually replace PostsScorer.
    """
    def __init__(self, 
                 validator: Any, 
                 scoring_hardware_config: Optional[HardwareConfig] = None,
                 shap_hardware_config: Optional[HardwareConfig] = None,
                 scoring_strategy: Optional[BaseScoringStrategy] = None):
        # Initialize configurations
        self.scoring_config = scoring_hardware_config or PerformanceConfig.get_config()
        self.shap_config = shap_hardware_config or self.scoring_config
        self.weights = ScoringWeights()
        
        # Initialize components
        self.validator = validator
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.semantic_scorer = SemanticScorer(self.scoring_config)
        self.engagement_scorer = EngagementScorer(self.weights)
        self.profile_scorer = ProfileScorer()
        self.feature_calculator = FeatureImportanceCalculator(
            config=self.shap_config,
            weights=self.weights,
            semantic_scorer=self.semantic_scorer
        )
        
        # Initialize scoring strategy
        self.scoring_strategy = scoring_strategy or DefaultScoringStrategy(self.weights)
        
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
        """Calculate individual post score using the scoring strategy"""
        text = post.get("Text", "")
        
        # Get verification status
        user_id = post.get("UserID")
        is_verified = False
        if user_id:
            agent = next(
                (agent for agent in self.validator.registered_agents.values() 
                 if agent.UserID == user_id),
                None
            )
            is_verified = bool(agent and agent.IsVerified)
        
        # Calculate component scores
        profile_score = self.profile_scorer.calculate_score(post)
        text_length_ratio = min(len(str(text)), 280) / 280
        engagement_score = self.engagement_scorer.calculate_score(post)
        
        return self.scoring_strategy.calculate_post_score(
            semantic_score=semantic_score,
            engagement_score=engagement_score,
            profile_score=profile_score,
            text_length_ratio=text_length_ratio,
            is_verified=is_verified
        )

    def calculate_scores(self, posts: List[Tweet]) -> Tuple[Dict[int, float], Dict[str, float]]:
        """Calculate agent scores from posts."""
        if not posts:
            logger.warning("No posts provided for scoring")
            return {}, {}
            
        try:
            # Step 1: Filter posts
            filtered_posts = self._filter_recent_posts(posts)
            stats = self._calculate_post_stats(filtered_posts)
            
            # Step 2: Process posts by agent and verification status
            verified_posts_by_uid = {}
            unverified_posts_by_uid = {}
            
            for post in filtered_posts:
                uid = self._get_agent_uid(post)
                if not uid:
                    continue
                    
                if post.get("IsVerified", False):
                    if uid not in verified_posts_by_uid:
                        verified_posts_by_uid[uid] = []
                    verified_posts_by_uid[uid].append(post)
                else:
                    if uid not in unverified_posts_by_uid:
                        unverified_posts_by_uid[uid] = []
                    unverified_posts_by_uid[uid].append(post)
            
            progress_config = ScoringProgressConfig(
                total_agents=len(verified_posts_by_uid) + len(unverified_posts_by_uid)
            )
            
            with progress_config.create_progress_bar() as main_pbar:
                main_pbar.set_postfix(**stats)
                
                # Calculate raw scores
                verified_scores = self._calculate_agent_scores(verified_posts_by_uid, main_pbar)
                unverified_scores = self._calculate_agent_scores(unverified_posts_by_uid, main_pbar)
                
                # Find the minimum verified score (if any verified accounts exist)
                min_verified_score = min(verified_scores.values()) if verified_scores else 1.0
                
                # Scale unverified scores to be strictly less than minimum verified score
                max_unverified = max(unverified_scores.values()) if unverified_scores else 0.0
                if max_unverified > 0:
                    scale_factor = (min_verified_score * 0.5) / max_unverified  # Ensure unverified scores are at most half of min verified
                    unverified_scores = {uid: score * scale_factor for uid, score in unverified_scores.items()}
                
                # Combine scores
                final_scores = {**verified_scores, **unverified_scores}
                
                # Calculate feature importance
                shap_config = ShapProgressConfig(total_samples=self.shap_config.shap_background_samples)
                with shap_config.create_progress_bar() as shap_pbar:
                    feature_importance = self.feature_calculator.calculate(
                        filtered_posts, 
                        progress_bar=shap_pbar
                    )
                    
                return final_scores, feature_importance
                
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

    def _calculate_agent_scores(self, 
                              posts_by_uid: Dict[int, List[Tweet]], 
                              progress_bar: tqdm) -> Dict[int, float]:
        """Calculate final scores for each agent"""
        final_scores = {uid: 0.0 for uid in posts_by_uid.keys()}
        start_time = time()
        processed_agents = 0
        
        # Calculate initial scores
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

        # Apply normalization
        final_scores = self.scoring_strategy.normalize_scores(final_scores)
        return final_scores

    def _get_agent_uid(self, post: Tweet) -> Optional[int]:
        """Get agent UID from post UserID"""
        user_id = post.get("UserID")
        if not user_id:
            return None
        
        # Convert registered agents to UserID -> UID mapping
        user_id_to_uid = {
            agent.UserID: int(agent.UID)
            for agent in self.validator.registered_agents.values()
        }
        
        return user_id_to_uid.get(user_id)

# For backward compatibility
class PostsScorer(AgentScorer):
    """
    Legacy class maintained for backward compatibility.
    Inherits from AgentScorer but keeps the old name.
    """
    def calculate_agent_scores(self, posts: List[Tweet]) -> Tuple[Dict[int, float], Dict[str, float]]:
        """Maintain old method name for compatibility"""
        return self.calculate_scores(posts)
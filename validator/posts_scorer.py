from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, UTC, timedelta
from interfaces.types import Tweet
from fiber.logging_utils import get_logger
from .semantic_scorer import SemanticScorer
from tqdm import tqdm
import shap
import pandas as pd
import torch
import psutil
from dataclasses import dataclass

logger = get_logger(__name__)


@dataclass
class HardwareConfig:
    """Hardware configuration for performance tuning"""
    batch_size: int
    max_samples: int
    shap_background_samples: int
    shap_nsamples: int
    device_type: str  # 'cpu', 'mps', 'cuda'
    gpu_memory: Optional[int] = None  # GPU memory in GB, if applicable

class PerformanceConfig:
    """Performance configuration profiles for different hardware specs"""
    
    # Default CPU settings
    DEFAULT_CPU = HardwareConfig(
        batch_size=512,
        max_samples=1000,
        shap_background_samples=100,
        shap_nsamples=100,
        device_type='cpu'
    )
    
    # Apple Silicon Configurations
    M_SERIES = {
        32: HardwareConfig(
            batch_size=1024,
            max_samples=4000,
            shap_background_samples=400,
            shap_nsamples=200,
            device_type='mps'
        ),
        64: HardwareConfig(  # Optimized for M3 Max
            batch_size=2048,
            max_samples=8000,
            shap_background_samples=500,
            shap_nsamples=250,
            device_type='mps'
        ),
        96: HardwareConfig(
            batch_size=4096,
            max_samples=12000,
            shap_background_samples=1000,
            shap_nsamples=500,
            device_type='mps'
        )
    }
    
    # NVIDIA GPU Configurations
    NVIDIA_GPU = {
        8: HardwareConfig(  # 8GB GPU
            batch_size=2048,
            max_samples=5000,
            shap_background_samples=500,
            shap_nsamples=250,
            device_type='cuda',
            gpu_memory=8
        ),
        12: HardwareConfig(  # 12GB GPU
            batch_size=4096,
            max_samples=10000,
            shap_background_samples=1000,
            shap_nsamples=500,
            device_type='cuda',
            gpu_memory=12
        ),
        24: HardwareConfig(  # 24GB GPU
            batch_size=8192,
            max_samples=20000,
            shap_background_samples=2000,
            shap_nsamples=1000,
            device_type='cuda',
            gpu_memory=24
        ),
        48: HardwareConfig(  # 48GB GPU
            batch_size=16384,
            max_samples=40000,
            shap_background_samples=4000,
            shap_nsamples=2000,
            device_type='cuda',
            gpu_memory=48
        )
    }
    
    @staticmethod
    def get_gpu_memory_gb() -> Optional[int]:
        """Get GPU memory in GB if CUDA is available"""
        if torch.cuda.is_available():
            try:
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                return int(gpu_memory / (1024**3))  # Convert bytes to GB
            except:
                return None
        return None

    @staticmethod
    def get_config(ram_override: Optional[int] = None, 
                  gpu_memory_override: Optional[int] = None) -> HardwareConfig:
        """
        Get the appropriate configuration based on system hardware
        Args:
            ram_override: Optional RAM amount in GB to override system detection
            gpu_memory_override: Optional GPU memory in GB to override detection
        Returns:
            HardwareConfig with appropriate settings
        """
        # Detect hardware
        if gpu_memory_override is not None:
            gpu_memory = gpu_memory_override
        else:
            gpu_memory = PerformanceConfig.get_gpu_memory_gb()

        total_ram = ram_override or (psutil.virtual_memory().total / (1024 ** 3))

        # CUDA GPU available
        if torch.cuda.is_available() and gpu_memory:
            # Find the closest GPU configuration
            gpu_configs = sorted(PerformanceConfig.NVIDIA_GPU.keys())
            for gpu_size in gpu_configs:
                if gpu_memory <= gpu_size:
                    return PerformanceConfig.NVIDIA_GPU[gpu_size]
            # If GPU is larger than our largest config, use the highest
            return PerformanceConfig.NVIDIA_GPU[gpu_configs[-1]]

        # Apple Silicon
        elif torch.backends.mps.is_available():
            ram_configs = sorted(PerformanceConfig.M_SERIES.keys())
            for ram_size in ram_configs:
                if total_ram <= ram_size:
                    return PerformanceConfig.M_SERIES[ram_size]
            # If RAM is larger than our largest config, use the highest
            return PerformanceConfig.M_SERIES[ram_configs[-1]]

        # CPU only
        else:
            return PerformanceConfig.DEFAULT_CPU

class PostsScorer:
    def __init__(self, validator: Any, hardware_config: Optional[HardwareConfig] = None):
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

        # Initialize hardware configuration
        self.config = hardware_config or PerformanceConfig.get_config()
        logger.info(f"Initialized with hardware config: {self.config}")
        logger.info(f"Using device type: {self.config.device_type}")
        if self.config.gpu_memory:
            logger.info(f"GPU Memory: {self.config.gpu_memory}GB")

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

    def _calculate_feature_importance(self, posts: List[Tweet]) -> Dict[str, float]:
        """Calculate SHAP values with hardware acceleration"""
        if len(posts) > self.config.max_samples:
            posts = np.random.choice(posts, self.config.max_samples, replace=False)
        
        # Move calculations to appropriate device and ensure float32
        device = torch.device(self.config.device_type)
        
        features = []
        scores = []
        
        # Use configured batch size
        for i in range(0, len(posts), self.config.batch_size):
            batch = posts[i:i + self.config.batch_size]
            batch_features = [{
                'text_length': len(str(post.get('Text', ''))),
                'likes': post.get('Likes', 0),
                'retweets': post.get('Retweets', 0),
                'replies': post.get('Replies', 0),
                'views': post.get('Views', 0),
            } for post in batch]
            features.extend(batch_features)
            
            # Calculate scores in batches using float32
            batch_scores = torch.tensor([
                np.float32(np.log1p(
                    f['text_length'] * self.length_weight +
                    f['likes'] * self.engagement_weights['Likes'] +
                    f['retweets'] * self.engagement_weights['Retweets'] +
                    f['replies'] * self.engagement_weights['Replies'] +
                    f['views'] * self.engagement_weights['Views']
                )) for f in batch_features
            ], device=device, dtype=torch.float32)
            
            scores.extend(batch_scores.cpu().numpy())
        
        if not features:
            return {}
            
        df = pd.DataFrame(features)
        
        # Fix SHAP warnings by explicitly setting l1_reg
        def score_func(X):
            X_tensor = torch.tensor(X, device=device, dtype=torch.float32)
            return np.array([np.log1p(
                row['text_length'] * self.length_weight +
                row['likes'] * self.engagement_weights['Likes'] +
                row['retweets'] * self.engagement_weights['Retweets'] +
                row['replies'] * self.engagement_weights['Replies'] +
                row['views'] * self.engagement_weights['Views']
            ) for _, row in pd.DataFrame(X, columns=df.columns).iterrows()])
        
        # Use explicit l1_reg parameter and ensure float32 dtype
        explainer = shap.KernelExplainer(
            score_func, 
            shap.sample(df, self.config.shap_background_samples).astype(np.float32),
            l1_reg='num_features(10)'  # Fix for SHAP warning
        )
        shap_values = explainer.shap_values(
            df.astype(np.float32), 
            nsamples=self.config.shap_nsamples
        )
        
        feature_importance = {
            feature: float(np.abs(shap_values[:, i]).mean())
            for i, feature in enumerate(df.columns)
        }
        
        return feature_importance

    def calculate_agent_scores(self, posts: List[Tweet]) -> Tuple[Dict[int, float], Dict[str, float]]:
        if not posts:
            logger.warning("No posts provided for scoring")
            return {}
            
        # Create overall progress bar
        total_steps = 4  # Total major steps in the process
        with tqdm(total=total_steps, desc="Scoring Process", unit="step") as main_pbar:
            # Step 1: Initial filtering and setup
            current_time = datetime.now(UTC)
            scoring_window = timedelta(days=7)
            
            filtered_posts = [
                post for post in posts 
                if (current_time - datetime.fromtimestamp(post.get("Timestamp", 0), UTC)) <= scoring_window
            ]
            
            stats = {
                "total_posts": len(posts),
                "filtered_posts": len(filtered_posts),
                "unique_users": len(set(post.get("UserID") for post in filtered_posts)),
                "posts_with_text": len([p for p in filtered_posts if p.get("Text")])
            }
            
            main_pbar.set_postfix({"stage": "Setup Complete", **stats})
            main_pbar.update(1)

            # Step 2: Process user mappings and group posts
            user_id_to_uid = {
                agent.UserID: int(agent.UID)
                for agent in self.validator.registered_agents.values()
            }
            
            final_scores = {uid: 0.0 for uid in user_id_to_uid.values()}
            posts_by_uid = {}
            all_texts = []
            text_to_post_map = {}

            for post in filtered_posts:
                user_id = post.get("UserID")
                if not user_id or user_id not in user_id_to_uid:
                    continue
                uid = user_id_to_uid[user_id]
                if uid not in posts_by_uid:
                    posts_by_uid[uid] = []
                posts_by_uid[uid].append(post)
                
                text = post.get("Text", "")
                if text:
                    all_texts.append(text)
                    if uid not in text_to_post_map:
                        text_to_post_map[uid] = []
                    text_to_post_map[uid].append(len(all_texts) - 1)

            main_pbar.set_postfix({"stage": "Posts Grouped", "agents": len(posts_by_uid)})
            main_pbar.update(1)

            # Step 3: Calculate semantic scores
            semantic_scores = self.semantic_scorer.calculate_scores(
                all_texts, 
                batch_size=self.config.batch_size,
                progress_bar=main_pbar  # Pass the main progress bar to semantic scorer
            )
            
            main_pbar.set_postfix({"stage": "Semantic Scoring Complete"})
            main_pbar.update(1)

            # Step 4: Calculate final scores
            for uid, agent_posts in posts_by_uid.items():
                if not agent_posts:
                    continue
                
                agent_semantic_scores = [
                    semantic_scores[idx] 
                    for idx in text_to_post_map.get(uid, [])
                ]
                
                if not agent_semantic_scores:
                    continue
                
                scores = []
                for post, semantic_score in zip(agent_posts, agent_semantic_scores):
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

            # Handle normalization and feature importance calculation
            scores_array = np.array(list(final_scores.values())).reshape(-1, 1)
            scores_array = np.nan_to_num(scores_array, nan=0.0, posinf=100.0, neginf=0.0)
            
            non_zero_scores = [score for score in scores_array.flatten() if score > 0]
            if len(non_zero_scores) > 1:
                try:
                    normalized_scores = self.scaler.fit_transform(scores_array).flatten()
                    final_scores = {
                        uid: score for uid, score in zip(final_scores.keys(), normalized_scores)
                    }
                except Exception as e:
                    logger.error(f"Error during score normalization: {str(e)}")
                    final_scores = {
                        uid: score for uid, score in zip(final_scores.keys(), scores_array.flatten())
                    }

            main_pbar.set_postfix({
                "stage": "Complete",
                "agents_scored": len(non_zero_scores),
                "total_agents": len(final_scores)
            })
            main_pbar.update(1)

            # Calculate feature importance
            feature_importance = self._calculate_feature_importance(filtered_posts)
            
            return final_scores, feature_importance

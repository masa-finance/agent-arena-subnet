import pytest
from datetime import datetime, UTC, timedelta
from validator.get_agent_posts import GetAgentPosts
from validator.agent_scorer import PerformanceConfig, HardwareConfig
import json
import torch
import logging

logger = logging.getLogger(__name__)

def get_optimal_config() -> HardwareConfig:
    """Get the optimal hardware configuration for the current system"""
    if torch.cuda.is_available():
        gpu_memory = PerformanceConfig.get_gpu_memory_gb()
        if gpu_memory:
            logger.info(f"CUDA GPU detected with {gpu_memory}GB memory")
            return PerformanceConfig.get_config(gpu_memory_override=gpu_memory)
    elif torch.backends.mps.is_available():
        import psutil
        total_ram = psutil.virtual_memory().total / (1024 ** 3)  # GB
        logger.info(f"Apple Silicon detected with {int(total_ram)}GB RAM")
        return PerformanceConfig.get_config(ram_override=int(total_ram))
    else:
        logger.info("Using CPU configuration")
        return PerformanceConfig.DEFAULT_CPU

@pytest.mark.asyncio
async def test_get_posts_last_20_mins():
    # Get optimal hardware configuration
    config = get_optimal_config()
    logger.info(f"\n=== Hardware Configuration ===")
    logger.info(f"Device Type: {config.device_type}")
    logger.info(f"Batch Size: {config.batch_size}")
    logger.info(f"Max Samples: {config.max_samples}")
    logger.info(f"SHAP Background Samples: {config.shap_background_samples}")
    logger.info(f"SHAP N-Samples: {config.shap_nsamples}")
    if config.gpu_memory:
        logger.info(f"GPU Memory: {config.gpu_memory}GB")
    
    # Setup time range for last 20 minutes
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(minutes=120)
    
    # Initialize PostsGetter with the time range
    posts_getter = GetAgentPosts(
        netuid=59,
        start_date=start_date,
        end_date=end_date
    )
    
    # Fetch posts
    posts = await posts_getter.get()
    
    # Basic assertions
    assert isinstance(posts, list), "Posts should be returned as a list"
    
    # Import constants directly from the module
    from validator.get_agent_posts import API_VERSION, SUBNET_API_PATH
    
    # Log the full API response and endpoint details
    logger.info("\n=== API Configuration ===")
    logger.info(f"Endpoint: {posts_getter.api_url}")
    logger.info(f"API Version: {API_VERSION}")
    logger.info(f"Subnet Path: {SUBNET_API_PATH}")
    
    logger.info("\n=== Request Details ===")
    logger.info(f"Time Range: {start_date.isoformat()} to {end_date.isoformat()}")
    logger.info(f"Total Posts: {len(posts)}")
    
    # Log sample posts (limit to 3 for readability)
    if posts:
        logger.info("\n=== Sample Posts ===")
        for i, post in enumerate(posts[:3], 1):
            logger.info(f"\nPost {i}:")
            logger.info(f"UserID: {post.get('UserID')}")
            logger.info(f"Text: {post.get('Text', '')[:100]}...")  # First 100 chars
            logger.info("Engagement Metrics:")
            logger.info(f"- Likes: {post.get('Likes', 0)}")
            logger.info(f"- Retweets: {post.get('Retweets', 0)}")
            logger.info(f"- Replies: {post.get('Replies', 0)}")
            logger.info(f"- Views: {post.get('Views', 0)}")
    
    # If there are posts, verify basic structure
    if posts:
        sample_post = posts[0]
        assert isinstance(sample_post, dict), "Each post should be a dictionary"

# Run with: pytest tests/test_get_agent_posts.py -v -s
import pytest
from datetime import datetime, UTC, timedelta
import json
from typing import Dict, Any
import httpx
import os
import numpy as np
import signal
import sys
from contextlib import contextmanager

from fiber.logging_utils import get_logger
from validator.agent_scorer import PostsScorer
from validator.get_agent_posts import GetAgentPosts
from validator.registration import ValidatorRegistration
from validator.config.hardware_config import HardwareConfig

logger = get_logger(__name__)

class MockValidator:
    def __init__(self):
        self.registered_agents = {}
        self.httpx_client = httpx.AsyncClient()
        self.netuid = 59
        
        # Add API key from environment
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            logger.warning("No API_KEY found in environment variables")
            
        # Add other required properties
        self.subtensor_network = "finney"
        self.subtensor_address = "wss://entrypoint-finney.opentensor.ai:443"
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.httpx_client.aclose()

    def _filter_agent_fields(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out unexpected fields from agent data before creating RegisteredAgentResponse"""
        expected_fields = {
            'ID', 'HotKey', 'UID', 'SubnetID', 'Version', 'UserID', 'Username', 
            'Avatar', 'Name', 'IsVerified', 'IsActive', 'FollowersCount',
            'VerificationTweetID', 'VerificationTweetURL', 'VerificationTweetTimestamp',
            'VerificationTweetText', 'CreatedAt', 'UpdatedAt', 'Banner', 'Biography',
            'Birthday', 'FollowingCount', 'FriendsCount', 'IsPrivate', 'Joined',
            'LikesCount', 'ListedCount', 'Location', 'PinnedTweetIDs', 'TweetsCount',
            'URL', 'Website', 'Emissions', 'Marketcap'
        }
        return {k: v for k, v in agent_data.items() if k in expected_fields}

class GracefulKiller:
    kill_now = False
    
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        logger.info("\nShutting down gracefully...")

@contextmanager
def graceful_shutdown():
    killer = GracefulKiller()
    try:
        yield killer
    finally:
        logger.info("Cleanup complete")

@pytest.mark.asyncio
async def test_live_scoring_with_registered_agents():
    """
    Test scoring using real API data and registered agents.
    This test:
    1. Fetches real registered agents
    2. Gets actual posts from the API
    3. Calculates scores using the real scoring algorithm
    4. Provides detailed output of the scoring process
    """
    
    # Set end time to now
    end_time = datetime.now(UTC)
    # Set start time to 7 days ago
    start_time = end_time - timedelta(days=7)
    
    logger.info("Time Range: %s to %s", start_time.isoformat(), end_time.isoformat())
    
    async with MockValidator() as validator:
        with graceful_shutdown() as killer:
            try:
                # Initialize components
                registrar = ValidatorRegistration(validator=validator)
                await registrar.fetch_registered_agents()
                
                logger.info("\n=== Test Configuration ===")
                logger.info(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}")
                logger.info(f"Number of registered agents: {len(validator.registered_agents)}")
                
                # Initialize scorers and getters
                posts_getter = GetAgentPosts(
                    netuid=59,
                    start_date=start_time,
                    end_date=end_time
                )

                # Configure separate hardware configs for scoring and SHAP
                scoring_config = HardwareConfig(
                    batch_size=2048,
                    max_samples=4000,
                    shap_background_samples=200,
                    shap_nsamples=100,
                    device_type='mps'
                )

                shap_config = HardwareConfig(
                    batch_size=1024,
                    max_samples=2000,
                    shap_background_samples=100,
                    shap_nsamples=50,
                    device_type='mps'
                )

                posts_scorer = PostsScorer(
                    validator,
                    scoring_hardware_config=scoring_config,
                    shap_hardware_config=shap_config
                )
                
                # Fetch real posts
                posts = await posts_getter.get()
                logger.info(f"Total Posts Fetched: {len(posts)}")
                
                # Print sample of posts for verification
                logger.info("\n=== Sample Posts ===")
                for idx, post in enumerate(posts[:3]):  # Show first 3 posts
                    logger.info(f"\nPost {idx + 1}:")
                    logger.info(f"UserID: {post.get('UserID', 'Unknown')}")
                    logger.info(f"Text: {post.get('Text', '')[:100]}...")  # First 100 chars
                    logger.info("Engagement Metrics:")
                    logger.info(f"- Likes: {post.get('Likes', 0)}")
                    logger.info(f"- Retweets: {post.get('Retweets', 0)}")
                    logger.info(f"- Replies: {post.get('Replies', 0)}")
                    logger.info(f"- Views: {post.get('Views', 0)}")
                
                # Calculate scores with shutdown check
                scores = None
                feature_importance = None
                try:
                    scores, feature_importance = posts_scorer.calculate_scores(posts)
                    if killer.kill_now:
                        logger.info("Scoring interrupted, saving partial results...")
                except KeyboardInterrupt:
                    logger.info("Received interrupt, cleaning up...")
                finally:
                    if scores:
                        logger.info(f"Processed {len(scores)} agents before shutdown")
                    # Add any cleanup code here
                    await validator.httpx_client.aclose()
                    
                # Print scoring results
                logger.info("\n=== Scoring Results ===")
                logger.info(f"Number of scored agents: {len(scores)}")
                
                # Enhanced SHAP value visualization
                logger.info("\n=== Feature Importance Analysis ===")
                
                # Sort features by importance
                sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
                
                # Calculate total importance for percentage calculation
                total_importance = sum(importance for _, importance in sorted_features)
                
                # Print detailed feature importance table
                logger.info("\nFeature Importance Breakdown:")
                logger.info("=" * 80)
                logger.info(f"{'Feature':<15} {'Importance':<12} {'Percentage':<12} {'Visualization'}")
                logger.info("=" * 80)
                
                for feature, importance in sorted_features:
                    percentage = (importance / total_importance) * 100
                    bar_length = int((importance / sorted_features[0][1]) * 40)  # Scale to 40 chars
                    bar = "█" * bar_length
                    logger.info(f"{feature:<15} {importance:>10.4f}   {percentage:>8.2f}%   {bar}")
                
                logger.info("=" * 80)
                
                # Print top contributing factors for highest scoring agents
                logger.info("\n=== Top Agent Analysis ===")
                top_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
                
                for uid, score in top_agents:
                    agent = next((a for a in validator.registered_agents.values() if int(a.UID) == uid), None)
                    if agent:
                        username = agent.Username if hasattr(agent, 'Username') else 'Unknown'
                        logger.info(f"\nAgent: @{username} (UID: {uid})")
                        logger.info(f"Total Score: {score:.4f}")
                        
                        # Get agent's posts
                        agent_posts = [p for p in posts if str(p.get('UserID')) == str(agent.UserID)]
                        if agent_posts:
                            avg_metrics = {
                                'text_length': np.mean([len(str(p.get('Text', ''))) for p in agent_posts]),
                                'likes': np.mean([p.get('Likes', 0) for p in agent_posts]),
                                'retweets': np.mean([p.get('Retweets', 0) for p in agent_posts]),
                                'replies': np.mean([p.get('Replies', 0) for p in agent_posts]),
                                'views': np.mean([p.get('Views', 0) for p in agent_posts])
                            }
                            
                            logger.info("Average Metrics:")
                            for metric, value in avg_metrics.items():
                                logger.info(f"- {metric}: {value:.2f}")
                
                # Print overall statistics
                logger.info("\n=== Overall Score Distribution ===")
                scores_array = np.array(list(scores.values()))
                percentiles = np.percentile(scores_array, [25, 50, 75])
                
                logger.info(f"Maximum score: {max(scores_array):.4f}")
                logger.info(f"75th percentile: {percentiles[2]:.4f}")
                logger.info(f"Median score: {percentiles[1]:.4f}")
                logger.info(f"25th percentile: {percentiles[0]:.4f}")
                logger.info(f"Minimum score: {min(scores_array):.4f}")
                logger.info(f"Average score: {np.mean(scores_array):.4f}")
                logger.info(f"Standard deviation: {np.std(scores_array):.4f}")

                # Basic assertions
                assert isinstance(scores, dict), "Scores should be returned as a dictionary"
                assert all(isinstance(score, float) for score in scores.values()), "All scores should be floats"
                assert all(0 <= score <= 1 for score in scores.values()), "All scores should be normalized between 0 and 1"
                
                # If we have scores, verify they make sense
                if scores:
                    assert max(scores.values()) <= 1.0, "Maximum score should not exceed 1.0"
                    assert min(scores.values()) >= 0.0, "Minimum score should not be below 0.0"
                    
                    logger.info("\n=== Score Statistics ===")
                    logger.info(f"Maximum score: {max(scores.values()):.4f}")
                    logger.info(f"Minimum score: {min(scores.values()):.4f}")
                    logger.info(f"Average score: {sum(scores.values()) / len(scores):.4f}")

            except Exception as e:
                logger.error(f"Error during test: {str(e)}")
                raise
            finally:
                logger.info("Test cleanup complete")

# Run with: pytest tests/test_posts_scorer.py -v -s
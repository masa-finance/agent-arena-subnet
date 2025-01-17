import pytest
from datetime import datetime, UTC, timedelta
import json
from typing import Dict, Any
import httpx
import os

from validator.posts_scorer import PostsScorer
from validator.get_agent_posts import GetAgentPosts
from validator.registration import ValidatorRegistration
from fiber.logging_utils import get_logger

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
        posts_scorer = PostsScorer(validator)
        
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
        
        # Calculate scores
        scores = posts_scorer.calculate_agent_scores(posts)
        
        # Print scoring results
        logger.info("\n=== Scoring Results ===")
        logger.info(f"Number of scored agents: {len(scores)}")
        
        # Sort scores by value for better readability
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        logger.info("\nDetailed Scores (sorted by score):")
        for uid, score in sorted_scores:
            agent_info = next(
                (agent for agent in validator.registered_agents.values() if str(agent.UID) == str(uid)),
                None
            )
            user_id = agent_info.UserID if agent_info else "Unknown"
            logger.info(f"Agent UID {uid} (UserID: {user_id}): Score = {score:.4f}")
        
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

# Run with: pytest tests/test_posts_scorer.py -v -s
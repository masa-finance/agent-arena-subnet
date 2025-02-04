import asyncio
import pytest
from datetime import datetime, UTC, timedelta
from validator.get_agent_posts import GetAgentPosts
from validator.scoring.scorers.semantic_scorer import SemanticScorer
from validator.config.scoring_config import ScoringWeights
from validator.config.progress_config import ProgressStages, ProgressBarConfig
from validator.registration import ValidatorRegistration
from fiber.logging_utils import get_logger
import numpy as np
from collections import defaultdict
from time import time
import torch
import httpx
import os

# Reference MockValidator from test_posts_scorer
class MockValidator:
    def __init__(self):
        self.registered_agents = {}
        self.httpx_client = httpx.AsyncClient()
        self.netuid = 59
        
        # Get API key from environment
        self.api_key = os.getenv("PROTOCOL_API_KEY")  # Changed to correct env var name
        if not self.api_key:
            logger.warning("No PROTOCOL_API_KEY found in environment variables")
            
        self.subtensor_network = "finney"
        self.subtensor_address = "wss://entrypoint-finney.opentensor.ai:443"
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.httpx_client.aclose()

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_semantic_scoring():
    """Test semantic scoring on all registered subnet 59 agents' posts from the last 24 hours."""
    
    try:
        # Initialize scoring config
        config = ScoringWeights()
        
        # Initialize mock validator and registration
        validator = MockValidator()
        registration = ValidatorRegistration(validator=validator)
        
        # Fetch registered agents
        await registration.fetch_registered_agents()  # Changed method name
        registered_agents = {
            agent.Username: agent 
            for agent in validator.registered_agents.values()
        }
        logger.info(f"Found {len(registered_agents)} registered agents on subnet 59")
        
        # Initialize posts getter for last 24 hours
        start_date = datetime.now(UTC) - timedelta(days=1)
        posts_getter = GetAgentPosts(
            netuid=59,
            start_date=start_date,
            end_date=datetime.now(UTC)
        )
        
        # Create progress bar for initialization
        init_progress = ProgressBarConfig(
            desc="Initialization",
            total=1,
            initial_status=ProgressStages.get_scoring_status(ProgressStages.INITIALIZATION)
        ).create_progress_bar()
        
        # Fetch posts
        all_posts = await posts_getter.get()
        init_progress.update(1)
        init_progress.close()
        
        if not all_posts:
            logger.error("No posts found in the last 24 hours")
            return
            
        # Group posts by agent (only for registered agents)
        agent_posts = defaultdict(list)
        for post in all_posts:
            username = post.get('Username')
            if username in registered_agents:
                agent_posts[username].append(post)
            
        logger.info(f"Analyzing posts from {len(agent_posts)} registered agents in the last 24 hours")
        
        # Log agents with no posts
        inactive_agents = set(registered_agents) - set(agent_posts.keys())
        if inactive_agents:
            logger.info(f"Found {len(inactive_agents)} registered agents with no posts in the last 24 hours")
        
        # Sort posts by timestamp
        for username, posts in agent_posts.items():
            posts.sort(key=lambda x: x.get('Timestamp', ''))
            
        # Initialize semantic scorer
        scorer = SemanticScorer(weights=config)
        
        # Extract text content from posts
        texts = [post.get('Text', '') for username, posts in agent_posts.items() for post in posts]
        
        # Create progress bar for semantic scoring
        scoring_progress = ProgressBarConfig(
            desc="Semantic Analysis",
            total=len(texts),
            initial_status=ProgressStages.get_semantic_status(0, len(texts))
        ).create_progress_bar()
        
        # Calculate scores for all posts
        scores = []
        start_time = time()
        for i, text in enumerate(texts):
            score = scorer.calculate_score(text)
            scores.append(score)
            
            # Update progress with rate
            elapsed = time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            scoring_progress.set_postfix(
                **ProgressStages.get_semantic_status(i + 1, len(texts), rate)
            )
            scoring_progress.update(1)
        
        scoring_progress.close()
        
        # Print results
        print(f"\n=== Semantic Analysis for all registered agents on subnet 59 over 24 Hours ===")
        print(f"Total Posts Analyzed: {len(texts)}")
        
        # Time-based analysis
        print("\nPost Frequency Analysis:")
        hours = defaultdict(int)
        for username, posts in agent_posts.items():
            for post in posts:
                timestamp = post.get('Timestamp')
                if not timestamp:
                    continue
                    
                # Handle different timestamp types
                try:
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp).replace(tzinfo=UTC)
                    elif isinstance(timestamp, int):
                        # Convert Unix timestamp (seconds since epoch)
                        dt = datetime.fromtimestamp(timestamp, tz=UTC)
                    elif isinstance(timestamp, datetime):
                        dt = timestamp.replace(tzinfo=UTC)
                    else:
                        logger.warning(f"Unexpected timestamp type: {type(timestamp)} for value: {timestamp}")
                        continue
                        
                    hours[dt.hour] += 1
                except (ValueError, TypeError, OSError) as e:
                    logger.warning(f"Error parsing timestamp {timestamp}: {str(e)}")
                    continue
        
        print("\nPosts by Hour (UTC):")
        for hour in range(24):
            if hours[hour] > 0:
                print(f"{hour:02d}:00 - {hour:02d}:59: {hours[hour]} posts")
        
        # Score analysis
        if scores:
            print(f"\nScore Statistics:")
            print(f"Average Score: {np.mean(scores):.3f}")
            print(f"Max Score: {max(scores):.3f}")
            print(f"Min Score: {min(scores):.3f}")
            print(f"Standard Deviation: {np.std(scores):.3f}")
            
            # Score distribution buckets
            buckets = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
            print("\nScore Distribution:")
            for i in range(len(buckets)-1):
                count = len([s for s in scores if buckets[i] <= s < buckets[i+1]])
                print(f"{buckets[i]:.1f} - {buckets[i+1]:.1f}: {count} posts ({(count/len(scores))*100:.2f}%)")
        
        # Content analysis
        print("\n=== Content Analysis ===")
        
        # Length analysis
        lengths = [len(post.get('Text', '').split()) for username, posts in agent_posts.items() for post in posts]
        print(f"\nWord Count Statistics:")
        print(f"Average Length: {np.mean(lengths):.1f} words")
        print(f"Max Length: {max(lengths)} words")
        print(f"Min Length: {min(lengths)} words")
        
        # Show top and bottom scoring posts
        print("\nTop 5 Most Original Posts:")
        scored_posts = list(zip(texts, scores))
        scored_posts.sort(key=lambda x: x[1], reverse=True)
        
        for text, score in scored_posts[:5]:
            print(f"\nScore: {score:.3f}")
            print(f"Text: {text[:100]}...")
            
        print("\nBottom 5 Scoring Posts:")
        for text, score in scored_posts[-5:]:
            print(f"\nScore: {score:.3f}")
            print(f"Text: {text[:100]}...")
        
        # Similarity analysis
        print("\n=== Content Similarity Analysis ===")
        print("Average similarity to previous post:")
        prev_embeddings = None
        similarities = []
        
        for i, text in enumerate(texts[1:], 1):
            curr_embedding = scorer.model.encode([text], convert_to_tensor=True)
            prev_embedding = scorer.model.encode([texts[i-1]], convert_to_tensor=True)
            similarity = torch.nn.functional.cosine_similarity(curr_embedding, prev_embedding)
            similarities.append(float(similarity))
        
        if similarities:
            print(f"Average similarity between consecutive posts: {np.mean(similarities):.3f}")
            print(f"Max similarity between consecutive posts: {max(similarities):.3f}")
            print(f"Min similarity between consecutive posts: {min(similarities):.3f}")
            
    except Exception as e:
        logger.error(f"Error in semantic scoring test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_semantic_scoring())
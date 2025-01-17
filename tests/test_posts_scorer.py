import pytest
from datetime import datetime, UTC, timedelta
import json
from typing import Dict, Any
import httpx
import os
import numpy as np
import pandas as pd

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

@pytest.mark.asyncio
async def test_live_scoring_with_registered_agents():
    """
    Test scoring using real API data and registered agents.
    """
    # Create results directory if it doesn't exist
    results_dir = "test_results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Generate timestamp for unique filename base
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(results_dir, f"scoring_results_{timestamp}.txt")
    feature_importance_csv = os.path.join(results_dir, f"feature_importance_{timestamp}.csv")
    agent_metrics_csv = os.path.join(results_dir, f"agent_metrics_{timestamp}.csv")
    
    def write_to_file(content: str):
        with open(results_file, "a") as f:
            f.write(content + "\n")
    
    # Set end time to now
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(days=7)
    
    write_to_file(f"Scoring Analysis Results - {timestamp}\n")
    write_to_file(f"Time Range: {start_time.isoformat()} to {end_time.isoformat()}\n")
    write_to_file("=" * 80 + "\n")
    
    async with MockValidator() as validator:
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
            
            # Calculate scores
            scores, feature_importance = posts_scorer.calculate_scores(posts)
            
            # Save feature importance to CSV
            feature_importance_df = pd.DataFrame([
                {
                    'Feature': feature,
                    'Importance': importance,
                    'Percentage': (importance / sum(feature_importance.values())) * 100
                }
                for feature, importance in sorted(
                    feature_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ])
            feature_importance_df.to_csv(feature_importance_csv, index=False)
            
            # Save text summary of feature importance
            write_to_file("\n=== Feature Importance Analysis ===\n")
            write_to_file("Feature Importance Breakdown:")
            write_to_file("=" * 80)
            write_to_file(f"{'Feature':<15} {'Importance':<12} {'Percentage':<12} {'Visualization'}")
            write_to_file("=" * 80)
            
            for _, row in feature_importance_df.iterrows():
                bar_length = int((row['Importance'] / feature_importance_df['Importance'].max()) * 40)
                bar = "█" * bar_length
                write_to_file(f"{row['Feature']:<15} {row['Importance']:>10.4f}   {row['Percentage']:>8.2f}%   {bar}")
            
            # Prepare agent metrics DataFrame
            agent_metrics = []
            for uid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                agent = next((a for a in validator.registered_agents.values() if int(a.UID) == uid), None)
                if agent:
                    agent_posts = [p for p in posts if str(p.get('UserID')) == str(agent.UserID)]
                    if agent_posts:
                        metrics = {
                            'Username': agent.Username,
                            'UID': uid,
                            'Total_Score': score,
                            'Post_Count': len(agent_posts),
                            'Avg_Text_Length': np.mean([len(str(p.get('Text', ''))) for p in agent_posts]),
                            'Avg_Likes': np.mean([p.get('Likes', 0) for p in agent_posts]),
                            'Avg_Retweets': np.mean([p.get('Retweets', 0) for p in agent_posts]),
                            'Avg_Replies': np.mean([p.get('Replies', 0) for p in agent_posts]),
                            'Avg_Views': np.mean([p.get('Views', 0) for p in agent_posts])
                        }
                        agent_metrics.append(metrics)
            
            # Save agent metrics to CSV
            agent_metrics_df = pd.DataFrame(agent_metrics)
            agent_metrics_df.to_csv(agent_metrics_csv, index=False)
            
            # Continue with text summary for readability
            write_to_file("\n=== Agent Analysis ===\n")
            for metrics in agent_metrics:
                write_to_file(f"\nAgent: @{metrics['Username']} (UID: {metrics['UID']})")
                write_to_file(f"Total Score: {metrics['Total_Score']:.4f}")
                write_to_file("Average Metrics:")
                for key, value in metrics.items():
                    if key not in ['Username', 'UID', 'Total_Score']:
                        write_to_file(f"- {key}: {value:.2f}")
            
            # Save overall statistics
            write_to_file("\n=== Overall Score Distribution ===")
            scores_array = np.array(list(scores.values()))
            percentiles = np.percentile(scores_array, [25, 50, 75])
            
            stats = {
                "Maximum score": max(scores_array),
                "75th percentile": percentiles[2],
                "Median score": percentiles[1],
                "25th percentile": percentiles[0],
                "Minimum score": min(scores_array),
                "Average score": np.mean(scores_array),
                "Standard deviation": np.std(scores_array)
            }
            
            for stat_name, value in stats.items():
                write_to_file(f"{stat_name}: {value:.4f}")
            
            logger.info(f"Results saved to:")
            logger.info(f"- Summary: {results_file}")
            logger.info(f"- Feature Importance: {feature_importance_csv}")
            logger.info(f"- Agent Metrics: {agent_metrics_csv}")
            
            # Continue with existing assertions
            assert isinstance(scores, dict)
            assert all(isinstance(score, float) for score in scores.values())
            assert all(0 <= score <= 1 for score in scores.values())
            
        except Exception as e:
            logger.error(f"Error during test: {str(e)}")
            write_to_file(f"\nError during test: {str(e)}")
            raise
        finally:
            write_to_file("\nTest completed at: " + datetime.now().isoformat())
            logger.info("Test cleanup complete")

# Run with: pytest tests/test_posts_scorer.py -v -s
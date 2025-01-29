import pytest
from datetime import datetime, UTC, timedelta
import json
from typing import Dict, Any, List, Tuple
import httpx
import os
import numpy as np
import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fiber.logging_utils import get_logger
from validator.scoring.agent_scorer import PostsScorer
from validator.get_agent_posts import GetAgentPosts
from validator.registration import ValidatorRegistration
from validator.config.hardware_config import HardwareConfig
from interfaces.types import Tweet

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
    Fetches only the last 24 hours of posts.
    """
    # Create dated results directory structure
    base_dir = "test_results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated_dir = datetime.now().strftime("%Y%m%d")
    results_dir = os.path.join(base_dir, dated_dir, timestamp)
    os.makedirs(results_dir, exist_ok=True)
    
    # Define file paths in the dated directory
    results_file = os.path.join(results_dir, "scoring_results.txt")
    feature_importance_csv = os.path.join(results_dir, "feature_importance.csv")
    agent_metrics_csv = os.path.join(results_dir, "agent_metrics.csv")
    
    # Create a metadata file to track test configuration
    metadata_file = os.path.join(results_dir, "metadata.json")
    
    def write_to_file(content: str):
        with open(results_file, "a") as f:
            f.write(content + "\n")
    
    # Set end time to now and start time to 24 hours ago
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=24)  # Changed from 7 days to 24 hours
    
    # Save metadata
    metadata = {
        "timestamp": timestamp,
        "date": dated_dir,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        },
        "files": {
            "scoring_results": "scoring_results.txt",
            "feature_importance": "feature_importance.csv",
            "agent_metrics": "agent_metrics.csv"
        }
    }
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
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
            
            # Immediately prepare and save agent metrics DataFrame
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
                            'Avg_Views': np.mean([p.get('Views', 0) for p in agent_posts]),
                            'FollowersCount': agent.FollowersCount,
                            'IsVerified': agent.IsVerified
                        }
                        agent_metrics.append(metrics)
            
            # Save agent metrics to CSV before SHAP calculation
            agent_metrics_df = pd.DataFrame(agent_metrics)
            agent_metrics_df.to_csv(agent_metrics_csv, index=False)
            
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
            
            # Add detailed SHAP analysis to scoring_results.txt
            write_to_file("\n=== SHAP Feature Importance Analysis ===\n")
            write_to_file("Feature Importance Breakdown (by category):")
            write_to_file("=" * 80 + "\n")
            
            # Group features by category - simplified to just Core features
            categories = {
                'Core': ['text_length_ratio', 'semantic_score', 'follower_score', 'is_verified',
                        'engagement_replies', 'engagement_likes', 'engagement_retweets', 'engagement_views']
            }
            
            for category, features in categories.items():
                write_to_file(f"\n{category} Features:")
                write_to_file("-" * 40)
                category_features = {
                    f: v for f, v in feature_importance.items() 
                    if f in features
                }
                if category_features:
                    total_importance = sum(category_features.values())
                    for feature, importance in sorted(
                        category_features.items(),
                        key=lambda x: x[1],
                        reverse=True
                    ):
                        percentage = (importance / sum(feature_importance.values())) * 100
                        category_percentage = (importance / total_importance) * 100
                        bar_length = int((importance / max(feature_importance.values())) * 40)
                        bar = "█" * bar_length
                        write_to_file(
                            f"{feature:<20} {importance:>8.4f} "
                            f"({percentage:>5.1f}% global, {category_percentage:>5.1f}% in category) {bar}"
                        )
                write_to_file("")
            
            # Add summary statistics
            write_to_file("\nSummary Statistics:")
            write_to_file("-" * 40)
            write_to_file(f"Total Features Analyzed: {len(feature_importance)}")
            write_to_file(f"Most Important Feature: {max(feature_importance.items(), key=lambda x: x[1])[0]}")
            write_to_file(f"Least Important Feature: {min(feature_importance.items(), key=lambda x: x[1])[0]}")
            
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
            
            logger.info(f"Results saved to directory: {results_dir}")
            logger.info(f"Files saved:")
            logger.info(f"- Summary: scoring_results.txt")
            logger.info(f"- Feature Importance: feature_importance.csv")
            logger.info(f"- Agent Metrics: agent_metrics.csv")
            logger.info(f"- Metadata: metadata.json")
            
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
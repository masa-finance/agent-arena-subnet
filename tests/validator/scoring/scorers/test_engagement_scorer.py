import asyncio
import pytest
from datetime import datetime, UTC, timedelta
from validator.get_agent_posts import GetAgentPosts
from validator.registration import ValidatorRegistration
from validator.scoring.scorers.engagement_scorer import EngagementScorer
from validator.config.scoring_config import ScoringWeights
from fiber.logging_utils import get_logger
import numpy as np

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_engagement_scoring():
    """Test engagement scoring on real posts from the last 5 days."""
    
    try:
        # Initialize scoring config
        config = ScoringWeights()
        
        # Initialize posts getter for last 5 days
        start_date = datetime.now(UTC) - timedelta(days=5)
        posts_getter = GetAgentPosts(
            netuid=59,
            start_date=start_date,
            end_date=datetime.now(UTC)
        )
        
        # Fetch posts
        posts = await posts_getter.get()
        if not posts:
            logger.error("No posts found in the last 5 days")
            return
            
        logger.info(f"Fetched {len(posts)} posts from the last 5 days")
        
        # Log engagement distribution
        engagement_stats = {
            "has_retweets": len([p for p in posts if p.get("Retweets", 0) > 0]),
            "has_replies": len([p for p in posts if p.get("Replies", 0) > 0]),
            "has_likes": len([p for p in posts if p.get("Likes", 0) > 0]),
            "has_views": len([p for p in posts if p.get("Views", 0) > 0])
        }
        logger.info("Engagement distribution:")
        for metric, count in engagement_stats.items():
            logger.info(f"{metric}: {count} posts ({(count/len(posts))*100:.2f}%)")
        
        # Initialize engagement scorer
        scorer = EngagementScorer(weights=config)
        
        # Initialize scorer with all posts for normalization
        scorer.initialize_scorer(posts)
        
        # Calculate scores for all posts
        scores = {}
        for post in posts:
            score = scorer.calculate_score(post)
            scores[str(post.get('id'))] = score

        # Sort posts by score for display
        scored_posts = [
            (post, scorer.calculate_score(post))  # Calculate score directly instead of using dict
            for post in posts
        ]
        scored_posts.sort(key=lambda x: x[1], reverse=True)
        
        # Print results
        print("\n=== Engagement Scores for Last 5 Days ===")
        print(f"Total Posts Analyzed: {len(posts)}")
        print("\nTop 10 Posts by Engagement Score:")
        print("-" * 80)
        
        for post, score in scored_posts[:10]:
            print(f"\nScore: {score:.3f}")
            print(f"Author: @{post.get('Username', 'unknown')}")
            print(f"Text: {post.get('Text', '')[:100]}...")
            print(f"Metrics: Retweets={post.get('Retweets', 0)}, "
                  f"Replies={post.get('Replies', 0)}, "
                  f"Likes={post.get('Likes', 0)}, "
                  f"Views={post.get('Views', 0)}")
            
            # Add score breakdown
            if score > 0:
                print("\nScore Breakdown:")
                for metric, weight in config.engagement_weights.items():
                    value = post.get(metric, 0)
                    if value > 0:
                        normalized = (np.log1p(value) / 
                                   np.log1p(scorer._max_metrics[metric]))
                        contribution = normalized * weight
                        print(f"{metric}: {value} -> {contribution:.3f}")
            print("-" * 80)
            
        # Print score distribution
        scores_list = [scorer.calculate_score(post) for post in posts]  # Calculate scores directly
        if scores_list:
            print(f"\nScore Statistics:")
            print(f"Average Score: {sum(scores_list) / len(scores_list):.3f}")
            print(f"Max Score: {max(scores_list):.3f}")
            print(f"Min Score: {min(scores_list):.3f}")
            
            # Add score distribution buckets
            buckets = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
            print("\nScore Distribution:")
            for i in range(len(buckets)-1):
                count = len([s for s in scores_list if buckets[i] <= s < buckets[i+1]])
                print(f"{buckets[i]:.1f} - {buckets[i+1]:.1f}: {count} posts ({(count/len(scores_list))*100:.2f}%)")
            
        # Find posts with highest engagement for each metric
        top_posts = {
            'Retweets': max(posts, key=lambda p: p.get('Retweets', 0)),
            'Replies': max(posts, key=lambda p: p.get('Replies', 0)),
            'Likes': max(posts, key=lambda p: p.get('Likes', 0)),
            'Views': max(posts, key=lambda p: p.get('Views', 0))
        }

        print("\n=== Maximum Engagement Posts ===")
        for metric, post in top_posts.items():
            print(f"\nTop {metric}:")
            print(f"Author: @{post.get('Username', 'unknown')}")
            print(f"Metrics: Retweets={post.get('Retweets', 0)}, "
                  f"Replies={post.get('Replies', 0)}, "
                  f"Likes={post.get('Likes', 0)}, "
                  f"Views={post.get('Views', 0)}")
            
            # Calculate and show detailed score for this post
            score = scorer.calculate_score(post)
            print(f"Score: {score:.3f}")

        # Sort by actual engagement totals for comparixson
        engagement_sorted = sorted(
            posts,
            key=lambda p: (
                p.get('Retweets', 0) * 0.4 +
                p.get('Replies', 0) * 0.3 +
                p.get('Likes', 0) * 0.2 +
                p.get('Views', 0) * 0.1
            ),
            reverse=True
        )

        print("\n=== Top 10 Posts by Raw Engagement ===")
        for post in engagement_sorted[:10]:
            score = scorer.calculate_score(post)
            print(f"\nScore: {score:.3f}")
            print(f"Author: @{post.get('Username', 'unknown')}")
            print(f"Metrics: Retweets={post.get('Retweets', 0)}, "
                  f"Replies={post.get('Replies', 0)}, "
                  f"Likes={post.get('Likes', 0)}, "
                  f"Views={post.get('Views', 0)}")
            
    except Exception as e:
        logger.error(f"Error in engagement scoring test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_engagement_scoring()) 
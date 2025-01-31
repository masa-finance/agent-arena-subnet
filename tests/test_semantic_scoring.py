import asyncio
import pytest
from datetime import datetime, UTC, timedelta
from validator.get_agent_posts import GetAgentPosts
from validator.scoring.scorers.semantic_scorer import SemanticScorer
from validator.config.scoring_config import ScoringWeights
from fiber.logging_utils import get_logger
import numpy as np
from collections import defaultdict
from validator.config.progress_config import ProgressStages, ProgressBarConfig
from tqdm import tqdm
from time import time

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_semantic_scoring():
    """Test semantic scoring on real posts from the last 24 hours."""
    
    try:
        # Initialize scoring config
        config = ScoringWeights()
        
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
        posts = await posts_getter.get()
        init_progress.update(1)
        init_progress.close()
        
        if not posts:
            logger.error("No posts found in the last 24 hours")
            return
            
        logger.info(f"Fetched {len(posts)} posts from the last 24 hours")
        
        # Initialize semantic scorer
        scorer = SemanticScorer(weights=config)
        
        # Extract text content from posts
        texts = [post.get('Text', '') for post in posts]
        
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
        
        # Sort posts by score for display
        scored_posts = list(zip(posts, scores))
        scored_posts.sort(key=lambda x: x[1], reverse=True)
        
        # Print results
        print("\n=== Semantic Scores for Last 24 Hours ===")
        print(f"Total Posts Analyzed: {len(posts)}")
        print("\nTop 10 Posts by Semantic Score:")
        print("-" * 80)
        
        for post, score in scored_posts[:10]:
            print(f"\nScore: {score:.3f}")
            print(f"Author: @{post.get('Username', 'unknown')}")
            print(f"Text: {post.get('Text', '')[:100]}...")
            print("-" * 80)
            
        # Print score distribution
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
        
        # Analyze content patterns
        print("\n=== Content Analysis ===")
        
        # Length analysis
        lengths = [len(post.get('Text', '').split()) for post in posts]
        print(f"\nWord Count Statistics:")
        print(f"Average Length: {np.mean(lengths):.1f} words")
        print(f"Max Length: {max(lengths)} words")
        print(f"Min Length: {min(lengths)} words")
        
        # Keyword stuffing analysis
        keyword_stuffing_count = len([
            score for score in scores 
            if score < config.semantic_config["keyword_threshold"]
        ])
        print(f"\nKeyword Stuffing Detection:")
        print(f"Posts with potential keyword stuffing: {keyword_stuffing_count} ({(keyword_stuffing_count/len(scores))*100:.2f}%)")
        
        # Content similarity analysis
        print("\n=== Content Similarity Analysis ===")
        print("\nMost Unique Posts (Lowest Similarity Scores):")
        unique_posts = sorted(scored_posts, key=lambda x: x[1], reverse=True)[:5]
        for post, score in unique_posts:
            print(f"\nUniqueness Score: {score:.3f}")
            print(f"Author: @{post.get('Username', 'unknown')}")
            print(f"Text: {post.get('Text', '')[:100]}...")
        
        # Group posts by author
        author_posts = defaultdict(list)
        for post, score in scored_posts:
            author_posts[post.get('Username', 'unknown')].append(score)
        
        # Author analysis
        print("\n=== Author Analysis ===")
        print("\nTop Authors by Average Semantic Score:")
        author_avg_scores = {
            author: np.mean(scores)
            for author, scores in author_posts.items()
            if len(scores) >= 3  # Only consider authors with at least 3 posts
        }
        
        for author, avg_score in sorted(author_avg_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
            post_count = len(author_posts[author])
            print(f"\nAuthor: @{author}")
            print(f"Average Score: {avg_score:.3f}")
            print(f"Posts: {post_count}")
            
    except Exception as e:
        logger.error(f"Error in semantic scoring test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_semantic_scoring()) 
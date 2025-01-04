import pytest
import json
from pathlib import Path
import numpy as np
from datetime import datetime, UTC
from protocol.scoring.agent_scorer import AgentScorer
from protocol.scoring.miner_weights import MinerWeights
from protocol.data_processing.post_loader import LoadPosts

def test_agent_scoring_with_real_data():
    """Test agent scoring using real data from posts.json"""
    
    # Initialize components
    agent_scorer = AgentScorer()
    miner_weights = MinerWeights(agent_scorer=agent_scorer)
    posts_loader = LoadPosts()
    
    # Load posts from the specified path
    current_time = datetime.now(UTC)
    posts = posts_loader.load_posts(
        timestamp_range=(
            int(current_time.timestamp() - 86400),  # Last 24 hours
            int(current_time.timestamp())
        )
    )
    
    # Force print for debugging
    import sys
    print("\n=== Agent Scoring Test Results ===", file=sys.stderr)
    print(f"Total posts loaded: {len(posts)}", file=sys.stderr)
    
    if len(posts) == 0:
        pytest.fail("No posts found in the specified time range")
    
    # Print sample of first post structure
    if len(posts) > 0:
        first_post = posts[0]
        print("\nFirst post structure:", file=sys.stderr)
        print(json.dumps(first_post, indent=2), file=sys.stderr)
        
        print("\nFirst post required fields:", file=sys.stderr)
        print(f"UID present: {first_post.get('uid') is not None}", file=sys.stderr)
        tweets = first_post.get('tweets', [])
        if tweets:
            tweet = tweets[0].get('Tweet', {})
            print(f"Timestamp present: {tweet.get('Timestamp') is not None}", file=sys.stderr)
            print(f"Likes present: {tweet.get('Likes') is not None}", file=sys.stderr)
            print(f"Retweets present: {tweet.get('Retweets') is not None}", file=sys.stderr)
            print(f"Replies present: {tweet.get('Replies') is not None}", file=sys.stderr)
            print(f"Views present: {tweet.get('Views') is not None}", file=sys.stderr)
            print(f"Text present: {tweet.get('Text') is not None}", file=sys.stderr)
    
    # Get final weights directly (this handles scoring internally)
    uids, weights = miner_weights.calculate_weights(posts)
    
    print(f"\nFinal weights calculated for {len(uids)} UIDs", file=sys.stderr)
    print("\nSample weights (top 3):", file=sys.stderr)
    sorted_weights = sorted(zip(uids, weights), key=lambda x: x[1], reverse=True)[:3]
    for uid, weight in sorted_weights:
        print(f"UID {uid}: {weight:.4f}", file=sys.stderr)
    
    # Basic assertions
    assert len(uids) > 0, "No agents were scored"
    assert all(0 <= w <= 1 for w in weights), "Weights must be between 0 and 1"
    assert len(uids) == len(weights), "Number of UIDs must match number of weights"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
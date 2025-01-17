import pytest
from datetime import datetime, UTC, timedelta
from validator.get_agent_posts import PostsGetter
import json

@pytest.mark.asyncio
async def test_get_posts_last_20_mins():
    # Setup time range for last 20 minutes
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(minutes=20)
    
    # Initialize PostsGetter with the time range
    posts_getter = PostsGetter(
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
    print("\n=== API Configuration ===")
    print(f"Endpoint: {posts_getter.api_url}")
    print(f"API Version: {API_VERSION}")
    print(f"Subnet Path: {SUBNET_API_PATH}")
    
    print("\n=== Request Details ===")
    print(f"Time Range: {start_date.isoformat()} to {end_date.isoformat()}")
    print(f"Total Posts: {len(posts)}")
    
    print("\n=== Response Body ===")
    print(json.dumps(posts, indent=2))
    
    # If there are posts, verify basic structure
    if posts:
        sample_post = posts[0]
        assert isinstance(sample_post, dict), "Each post should be a dictionary" 

# pytest tests/test_posts_getter.py -v -s to run the test and get the output with full response body
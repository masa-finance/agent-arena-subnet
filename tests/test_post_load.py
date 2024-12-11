import pytest
from protocol.data_processing.post_load import LoadPosts
from pathlib import Path
import json

@pytest.fixture
def posts_loader():
    """Fixture to provide LoadPosts instance"""
    return LoadPosts()

def test_load_real_data(posts_loader):
    """Test loading actual data from posts.json"""
    posts = posts_loader.load_posts()
    
    # Verify we got data
    assert isinstance(posts, list)
    assert len(posts) > 0
    
    # Test first post structure matches our actual data
    first_post = posts[0]
    assert first_post["uid"] == "1"
    assert first_post["user_id"] == "1470086780"
    assert first_post["subnet_id"] == "59"
    assert first_post["query"] == "(dogecoin) until:2024-12-11 since:2024-12-10"
    assert first_post["count"] == 2
    assert first_post["created_at"] == 1725519123
    
    # Verify tweets array
    assert isinstance(first_post["tweets"], list)
    assert len(first_post["tweets"]) == 2
    
    # Verify first tweet structure
    first_tweet = first_post["tweets"][0]["Tweet"]
    assert first_tweet["ID"] == "1831586071164907637"
    assert first_tweet["Text"] == "@Cyber_Dogecoin $300"
    assert first_tweet["UserID"] == "1470086780"
    assert first_tweet["Username"] == "stylustica"
    assert first_tweet["Timestamp"] == 1725519123
    
    # Verify second tweet structure
    second_tweet = first_post["tweets"][1]["Tweet"]
    assert second_tweet["ID"] == "1831585995717845039"
    assert second_tweet["Text"] == "@444worldeth Plot twist: they're actually secret agents for Dogecoin 🐕🚀"
    assert second_tweet["UserID"] == "2953786353"
    assert second_tweet["Username"] == "0ce5e50e4efd48c"

def test_filter_by_timestamp_range_real_data(posts_loader):
    """Test timestamp filtering with real data"""
    # Known timestamp from our data
    start_time = 1725519105  # Second tweet's timestamp
    end_time = 1725519123    # First tweet's timestamp
    
    posts = posts_loader.load_posts(timestamp_range=(start_time, end_time))
    assert len(posts) > 0
    
    # Verify timestamps fall within range for tweets
    for post in posts:
        tweet_timestamps = [tweet["Tweet"]["Timestamp"] for tweet in post["tweets"]]
        # At least one tweet should be within the range
        assert any(start_time <= ts <= end_time for ts in tweet_timestamps)

def test_filter_by_user_id_real_data(posts_loader):
    """Test user_id filtering with real data"""
    # Known user_id from our data
    user_id = "1470086780"
    
    posts = posts_loader.load_posts(user_id=user_id)
    assert len(posts) > 0
    
    # Verify all posts are from the specified user
    for post in posts:
        assert post["user_id"] == user_id

def test_filter_by_subnet_id_real_data(posts_loader):
    """Test subnet_id filtering with real data"""
    # Known subnet_id from our data
    subnet_id = "59"
    
    posts = posts_loader.load_posts(subnet_id=subnet_id)
    assert len(posts) > 0
    
    # Verify all posts are from the specified subnet
    for post in posts:
        assert post["subnet_id"] == subnet_id

def test_filter_by_created_at_range_real_data(posts_loader):
    """Test created_at filtering with real data"""
    # Known created_at from our data
    start_time = 1725519123  # From our sample data
    end_time = 1725519123    # Same time since we have one post
    
    posts = posts_loader.load_posts(created_at_range=(start_time, end_time))
    assert len(posts) > 0
    
    # Verify created_at falls within range
    for post in posts:
        assert start_time <= post["created_at"] <= end_time

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
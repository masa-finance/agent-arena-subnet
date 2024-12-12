import pytest
from protocol.data_processing.post_saver import PostSaver, Metadata
import json
from unittest.mock import Mock

# Fixture for PostSaver instance


@pytest.fixture
def post_saver(tmp_path):
    """Fixture to provide PostSaver instance with a temporary JSON storage file"""
    storage_path = tmp_path / "posts.json"
    return PostSaver(storage_path=str(storage_path))

# Test initialization of PostSaver


def test_post_saver_initialization(post_saver):
    """Test PostSaver initialization"""
    assert post_saver.storage_path.exists()

# Test saving a new post


def new_post(post_saver):
    """Test saving a new post to storage"""
    metadata: Metadata = {
        "uid": "1",
        "user_id": "123",
        "subnet_id": "456",
        "query": "test query",
        "count": 1,
        "created_at": 1234567890
    }
    response = {
        "data": [{"Tweet": {"ID": "1", "Text": "Test tweet"}}]
    }
    post_saver.save_post(response, metadata)
    with open(post_saver.storage_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def test_save_new_post(post_saver):
    """Test saving a new post to storage"""
    data = new_post(post_saver)

    assert len(data) == 1
    assert data[0]["uid"] == "1"
    assert data[0]["tweets"][0]["Tweet"]["ID"] == "1"

# Test handling of duplicate posts


def test_handle_duplicate_posts(post_saver):
    """Test that duplicate posts are not saved again"""
    metadata: Metadata = {
        "uid": "1",
        "user_id": "123",
        "subnet_id": "456",
        "query": "test query",
        "count": 1,
        "created_at": 1234567890
    }
    response = {
        "data": [{"Tweet": {"ID": "1", "Text": "Test tweet"}}]
    }
    # Save the post twice
    post_saver.save_post(response, metadata)
    post_saver.save_post(response, metadata)
    with open(post_saver.storage_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Ensure only one post is saved
    assert len(data) == 1

# Test file creation when it does not exist


def test_file_creation_on_save(post_saver, tmp_path):
    """Test that a new file is created if it does not exist when saving a post"""
    # Ensure the file does not exist
    post_saver.storage_path.unlink()
    assert not post_saver.storage_path.exists()

    # Save a new post which should create the file
    test_save_new_post(post_saver)
    assert post_saver.storage_path.exists()

# Test custom path configurations


def test_custom_path_configuration(tmp_path):
    """Test PostSaver with a custom storage path"""
    custom_path = tmp_path / "custom_posts.json"
    post_saver = PostSaver(storage_path=str(custom_path))

    print("CUSTOM PATH", custom_path)
    print("POST SAVER STORAGE PATH", post_saver.storage_path)
    assert post_saver.storage_path == custom_path

# Test error cases


def test_error_on_invalid_json(post_saver, tmp_path):
    """Test error handling when the JSON file contains invalid JSON"""
    # Delete the file first if it exists
    invalid_json_path = tmp_path / "invalid_posts.json"
    if invalid_json_path.exists():
        invalid_json_path.unlink()
    # Create an invalid JSON file
    invalid_json_path.write_text("This is not valid JSON", encoding='utf-8')

    post_saver = PostSaver(storage_path=str(invalid_json_path))

    try:
        post_saver.save_post({"data": [{"Tweet": {"ID": "1", "Text": "Test tweet"}}]}, {
            "uid": "1",
            "user_id": "123",
            "subnet_id": "456",
            "query": "test query",
            "count": 1,
            "created_at": 1234567890
        })
    except Exception:
        pass
# Test saving a post with no new tweets


def test_save_post_with_no_new_tweets(tmp_path):
    """Test saving a post that contains no new tweets"""

    custom_path = tmp_path / "test_save_post_with_no_new_tweets_posts.json"
    post_saver = PostSaver(storage_path=str(custom_path))

    metadata: Metadata = {
        "uid": "2",
        "user_id": "123",
        "subnet_id": "456",
        "query": "test query",
        "count": 1,
        "created_at": 1234567890
    }
    response = {
        "data": []  # No new tweets
    }

    test_save_new_post(post_saver)
    with open(post_saver.storage_path, 'r', encoding='utf-8') as f:
        pre_loaded_data = json.load(f)

        print("PRE LOADED DATA LENGTH: ", len(pre_loaded_data))

    post_saver.save_post(response, metadata)
    with open(post_saver.storage_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("POST LOADED DATA LENGTH: ", len(data))

    # Ensure no new post is added
    assert len(data) == len(pre_loaded_data)

# Test saving a post with some new and some duplicate tweets


def test_save_post_with_mixed_tweets(post_saver):
    """Test saving a post that contains both new and duplicate tweets"""

    if post_saver.storage_path.exists():
        post_saver.storage_path.unlink()

    metadata: Metadata = {
        "uid": "3",
        "user_id": "123",
        "subnet_id": "456",
        "query": "test query",
        "count": 2,
        "created_at": 1234567890
    }
    response = {
        "data": [
            {"Tweet": {"ID": "1", "Text": "Test tweet"}},  # Duplicate tweet
            {"Tweet": {"ID": "4287", "Text": "Another test tweet"}}  # New tweet
        ]
    }

    # Create fixture post
    test_save_new_post(post_saver)

    # Post a new tweet with dummy data and a duplicated tweet ID
    post_saver.save_post(response, metadata)
    with open(post_saver.storage_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find the post with the same uid as metadata
    post_with_same_uid = next(
        (post for post in data if post['uid'] == metadata['uid']), None)

    # Ensure the post with the same uid only has 1 tweet
    assert post_with_same_uid is not None
    assert len(post_with_same_uid['tweets']) == 1

# Add more tests as needed for other functionalities

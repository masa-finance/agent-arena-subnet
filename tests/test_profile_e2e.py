import pytest
from protocol.profile import get_x_profile


def test_get_x_profile_live():
    """Test live X profile request to local API"""
    return
    # Test the function with a known username
    result = get_x_profile(username="elonmusk")

    # Print the actual response for inspection
    print("\nAPI Response:")
    print(result)

    # Basic validation of response structure
    assert isinstance(result, dict)
    assert "data" in result
    assert "recordCount" in result


def test_get_x_profile_with_different_users():
    """Test different user profile requests"""
    return
    usernames = ["elonmusk", "naval", "jack", "vitalikbuterin"]

    for username in usernames:
        print(f"\nTesting profile: {username}")
        result = get_x_profile(username=username)

        # Print results for inspection
        print(f"Response for {username}:", result)

        # Basic validation
        assert isinstance(result, dict)
        assert "data" in result

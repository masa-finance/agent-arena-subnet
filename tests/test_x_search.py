import pytest
from protocol.x.search import search_x

def test_search_x_live():
    """Test live X search request to local API"""
    # Test the function with a simple query
    result = search_x(
        query="#Bitcoin",
        count=5,
        additional_params={
            "lang": "en"
        }
    )
    
    # Print the actual response for inspection
    print("\nAPI Response:")
    print(result)
    
    # Basic validation of response structure
    assert isinstance(result, dict)
    assert "data" in result
    assert "recordCount" in result
    
    # If data is returned, validate its structure
    if result["data"]:
        first_tweet = result["data"][0]
        assert "Tweet" in first_tweet
        assert "Error" in first_tweet
        
        # Validate Tweet structure
        tweet = first_tweet["Tweet"]
        assert "ID" in tweet
        assert "Text" in tweet

def test_search_x_with_different_queries():
    """Test different search queries"""
    queries = [
        "from:elonmusk",
        "#AI lang:en",
        "crypto",
        "blockchain"
    ]
    
    for query in queries:
        print(f"\nTesting query: {query}")
        result = search_x(query=query, count=2)
        
        # Handle potential None response
        if result is None:
            print(f"No results found for query: {query}")
            continue
            
        # Print results for inspection
        data = result.get('data')
        if data is None:
            print(f"No data found for query: {query}")
            continue
            
        print(f"Found {len(data)} tweets")
        
        # Basic validation
        assert isinstance(result, dict)
        assert "data" in result
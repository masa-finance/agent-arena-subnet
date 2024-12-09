import pytest
from datetime import datetime, timedelta
from protocol.x.masa import Masa
import time
from unittest.mock import patch
import os
import logging

# Configure logging to reduce noise
logging.getLogger('QCManager').setLevel(logging.ERROR)

class TestMasaXScraping:
    @pytest.fixture
    def masa_client(self):
        """Initialize Masa client with local test endpoint"""
        # Set up a test data directory
        test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
        os.makedirs(test_data_dir, exist_ok=True)
        
        # Initialize client with test configuration
        client = Masa(
            base_url="http://localhost:8000",
            data_directory=test_data_dir
        )
        return client
        
    @pytest.fixture
    def test_search_terms(self):
        """Sample search terms for testing"""
        return [
            "from:elonmusk",
            "#AI lang:en",
            "@naval -crypto",
            "blockchain OR crypto",
            "ai geocode:37.7749,-122.4194,10mi"
        ]

    def test_process_requests(self, masa_client, test_search_terms):
        """Test basic request processing"""
        # Prepare test requests
        requests = [
            {
                "scraper": "XTwitterScraper",
                "endpoint": "data/twitter/tweets/recent",
                "priority": 1,
                "params": {
                    "query": term,
                    "max_results": 10
                }
            }
            for term in test_search_terms
        ]
        
        # Process requests
        response = masa_client.process_requests(requests)
        
        # Verify response structure
        assert response is not None
        assert response["success"] is True
        assert "message" in response
        assert "requests" in response
        assert len(response["requests"]) == len(requests)
        
        # Verify each processed request
        for processed_request in response["requests"]:
            assert "id" in processed_request
            assert "status" in processed_request
            assert "request" in processed_request
            assert "created_at" in processed_request
            assert processed_request["status"] == "queued"
            
            # Verify the request format
            request = processed_request["request"]
            assert "type" in request
            assert "endpoint" in request
            assert "priority" in request
            assert "parameters" in request

    @pytest.mark.integration
    def test_scheduled_scraping(self, masa_client, test_search_terms):
        """Test scheduled scraping with a short interval"""
        # Set collection time to 1 minute from now
        now = datetime.now()
        collection_time = (now + timedelta(minutes=1)).strftime("%H:%M")
        
        # Mock time.sleep to avoid waiting
        with patch('time.sleep') as mock_sleep:
            masa_client.schedule_daily_x_scrape(
                search_terms=test_search_terms,
                collection_time=collection_time,
                max_results=10
            )
            
            # Verify sleep was called
            mock_sleep.assert_called()

    def test_list_requests(self, masa_client):
        """Test listing requests"""
        # First add some requests
        requests = [
            {
                "scraper": "XTwitterScraper",
                "endpoint": "data/twitter/tweets/recent",
                "priority": 1,
                "params": {
                    "query": "test query",
                    "max_results": 10
                }
            }
        ]
        
        # Process requests
        masa_client.process_requests(requests)
        
        # List requests
        masa_client.list_requests()
        
        # Test with status filter
        masa_client.list_requests(statuses=["queued"])

    def test_clear_requests(self, masa_client):
        """Test clearing requests"""
        # First add some requests
        requests = [
            {
                "scraper": "XTwitterScraper",
                "endpoint": "data/twitter/tweets/recent",
                "priority": 1,
                "params": {
                    "query": "test query",
                    "max_results": 10
                }
            }
        ]
        
        # Process requests
        response = masa_client.process_requests(requests)
        
        # Get request ID
        request_id = response["requests"][0]["id"]
        
        # Clear specific request
        masa_client.clear_requests([request_id])
        
        # Clear all requests
        masa_client.clear_requests()

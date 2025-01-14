import pytest
import time
import logging

from protocol.x.request import Request

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_request_queue_live():
    """Test live request queue with actual API calls"""
    logger.info("Starting live request queue test")

    # Initialize queue
    rq = Request(max_concurrent_requests=2)
    logger.debug("Created Request with max_concurrent_requests=2")

    rq.start()
    logger.debug("Started request queue processing thread")

    # Add test requests with different priorities
    test_requests = [
        ("search", {"query": "#Bitcoin"}, 1),
        ("profile", {"username": "elonmusk"}, 2),
        ("search", {"query": "#AI"}, 3),
    ]

    for req_type, data, priority in test_requests:
        logger.info(
            f"Adding request: type={req_type}, data={data}, priority={priority}"
        )
        rq.add_request(req_type, data, priority)

    # Wait for requests to process
    logger.debug("Waiting for requests to process...")
    time.sleep(5)  # Adjust based on API response times
    logger.info("Test completed")


def test_request_queue_priorities():
    """Test queue priority handling with mixed request types"""
    logger.info("Starting priority handling test")

    rq = Request(max_concurrent_requests=1)  # Single thread for predictable ordering
    logger.debug("Created Request with max_concurrent_requests=1")

    rq.start()
    logger.debug("Started request queue processing thread")

    # Add requests in non-priority order
    requests = [
        ("search", {"query": "#Crypto"}, 3),
        ("profile", {"username": "naval"}, 1),
        ("search", {"query": "#AI"}, 2),
    ]

    for req_type, data, priority in requests:
        logger.info(
            f"Adding request: type={req_type}, data={data}, priority={priority}"
        )
        rq.add_request(req_type, data, priority)

    # Wait for processing
    logger.debug("Waiting for requests to process...")
    time.sleep(5)  # Adjust based on API response times
    logger.info("Test completed")


def test_request_queue_concurrent():
    """Test concurrent request handling"""
    logger.info("Starting concurrent request handling test")

    rq = Request(max_concurrent_requests=3)
    logger.debug("Created Request with max_concurrent_requests=3")

    rq.start()
    logger.debug("Started request queue processing thread")

    # Add multiple requests simultaneously
    test_queries = ["#Bitcoin", "#Ethereum", "#AI", "#ML", "#Web3"]

    for query in test_queries:
        logger.info(f"Adding search request for query: {query}")
        rq.add_request("search", {"query": query}, priority=100)

    # Wait for processing
    logger.debug("Waiting for requests to process...")
    time.sleep(8)  # Adjust based on API response times
    logger.info("Test completed")


if __name__ == "__main__":
    # Run tests directly
    logger.info("Running tests directly")

    logger.info("\n=== Testing Live Request Queue ===")
    test_request_queue_live()

    logger.info("\n=== Testing Priority Handling ===")
    test_request_queue_priorities()

    logger.info("\n=== Testing Concurrent Requests ===")
    test_request_queue_concurrent()

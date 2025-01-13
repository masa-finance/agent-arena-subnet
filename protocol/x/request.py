import threading
import time
import logging
import os
from typing import Any, Dict
from dotenv import load_dotenv
import itertools

# Import the functions from their respective modules
from protocol.x.profile import get_x_profile

# Load environment variables
load_dotenv()

# Configure logging based on environment variable
log_level = logging.DEBUG if os.getenv("DEBUG", "").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_CONCURRENT_REQUESTS = 5  # Maximum parallel requests
DEFAULT_API_REQUESTS_PER_SECOND = 20  # Default to 20 RPS
DEFAULT_RETRIES = 10  # Number of retry attempts

BACKOFF_BASE_SLEEP = 1
THREAD_DAEMON = True  # Run worker threads as daemons


class Request:
    """A thread-safe priority queue system for handling different types of API requests.

    This class implements a multi-queue system that can handle different types of requests
    (search and profile) with priority levels, concurrent processing capabilities, and
    rate limiting. Priority values are ascending (lower numbers = higher priority, e.g., 0 is highest).

    Attributes:
        max_concurrent_requests (int): Maximum number of requests that can be processed simultaneously.
        queues (Dict[str, PriorityQueue]): Dictionary of priority queues for different request types.
        lock (threading.Lock): Thread lock for managing concurrent access.
        active_requests (int): Counter for currently processing requests.
        counter (itertools.count): Unique sequence counter for request ordering.
        requests_per_second (float): Maximum number of requests allowed per second.
        last_request_time (float): Timestamp of the last processed request.
        rate_limit_lock (threading.Lock): Thread lock for rate limiting.

    Example:
        >>> rq = Request(max_concurrent_requests=5)
        >>> rq.start()
        >>>
        >>> # Add a search request
        >>> rq.add_request(
        ...     data={'query': '#Bitcoin'},
        ...     priority=1
        ... )
        >>>
        >>> # Add a profile request
        >>> rq.add_request(
        ...     data={'username': 'elonmusk'},
        ...     priority=2
        ... )
    """

    def __init__(self, max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS):
        """Initialize the Request with specified concurrency and rate limits.

        Args:
            max_concurrent_requests (int, optional): Maximum number of concurrent requests.
                Defaults to DEFAULT_MAX_CONCURRENT_REQUESTS.
        """
        self.max_concurrent_requests = max_concurrent_requests
        self.lock = threading.Lock()
        self.active_requests = 0
        self.counter = itertools.count()  # Unique sequence count

        # Rate limiting attributes
        self.requests_per_second = DEFAULT_API_REQUESTS_PER_SECOND
        self.last_request_time = time.time()
        self.rate_limit_lock = threading.Lock()

        logger.debug(
            f"Initialized Request with max_concurrent_requests={max_concurrent_requests}, "
            f"rate_limit={self.requests_per_second} RPS"
        )

    async def execute(self, data: Dict[str, Any]):
        response = self._handle_request(data, True)
        return response

    def _wait_for_rate_limit(self):
        """Enforce rate limiting by waiting appropriate amount of time between requests.

        This method ensures that requests are spaced according to the requests_per_second
        setting. It uses a thread-safe lock to manage concurrent access to the rate limiter.
        """
        with self.rate_limit_lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            required_gap = 1.0 / self.requests_per_second

            if time_since_last_request < required_gap:
                sleep_time = required_gap - time_since_last_request
                logger.debug(
                    f"Rate limiting: sleeping for {
                             sleep_time:.2f} seconds"
                )
                time.sleep(sleep_time)

            self.last_request_time = time.time()

    def _handle_request(self, data: Dict[str, Any], quick_return=False):
        """Process a single request with error handling, retry mechanism, and rate limiting.

        Args:
            data (Dict[str, Any]): Request payload data.

        Note:
            This method enforces rate limiting before making the actual API request.
        """
        with self.lock:
            self.active_requests += 1
            logger.debug(f"Active requests increased to {self.active_requests}")

        try:
            self._wait_for_rate_limit()  # Apply rate limiting before making request

            response = get_x_profile(username=data["username"])

            if quick_return:
                return response

            if response["data"] is not None:
                logger.info(f"Processed request: {response}")

                metadata = {
                    "uid": data["metadata"].UID,
                    "user_id": data["metadata"].UserID,
                    "subnet_id": data["metadata"].SubnetID,
                    "query": data["query"],
                    "count": len(response),
                    "created_at": int(time.time()),
                }

                self.saver.save_post(response, metadata)
                return response, metadata

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self._retry_request(data)
        finally:
            with self.lock:
                self.active_requests -= 1
                logger.debug(
                    f"Active requests decreased to {
                             self.active_requests}"
                )

    def _retry_request(
        self,
        data: Dict[str, Any],
        retries: int = DEFAULT_RETRIES,
    ):
        """Retry failed requests with exponential backoff.

        Args:
            data (Dict[str, Any]): Request payload data.
            retries (int, optional): Maximum number of retry attempts.
                Defaults to DEFAULT_RETRIES.

        Note:
            Uses BACKOFF_BASE_SLEEP for the exponential backoff calculation.
            Delay = BACKOFF_BASE_SLEEP * (2 ^ attempt)
        """
        for attempt in range(retries):
            try:
                logger.warning(
                    f"Retrying request: {
                               data}, attempt {attempt + 1}"
                )
                # Exponential backoff
                time.sleep(BACKOFF_BASE_SLEEP * (2**attempt))
                return
            except Exception as e:
                logger.error(f"Retry failed: {e}")
        logger.error(
            f"Request failed after {
                     retries} attempts: {data}"
        )


if __name__ == "__main__":

    rq = Request()
    time.sleep(10)  # Keep the main thread alive to allow processing

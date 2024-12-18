import queue
import threading
import time
import logging
import os
from typing import Any, Dict, Callable, Optional
from dotenv import load_dotenv
import itertools

# Import the functions from their respective modules
from protocol.x.profile import get_x_profile
from protocol.x.search import search_x
from protocol.data_processing.post_saver import PostSaver

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

# Base priority level (higher = lower priority)
DEFAULT_PRIORITY = 100
# Base delay (seconds) for exponential backoff
BACKOFF_BASE_SLEEP = 1
THREAD_DAEMON = True  # Run worker threads as daemons

POSTS_STORAGE_PATH = os.getenv("POSTS_STORAGE_PATH", "data/posts.json")


class RequestQueue:
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
        >>> rq = RequestQueue(max_concurrent_requests=5)
        >>> rq.start()
        >>>
        >>> # Add a search request
        >>> rq.add_request(
        ...     request_type='search',
        ...     request_data={'query': '#Bitcoin'},
        ...     priority=1
        ... )
        >>>
        >>> # Add a profile request
        >>> rq.add_request(
        ...     request_type='profile',
        ...     request_data={'username': 'elonmusk'},
        ...     priority=2
        ... )
    """

    def __init__(self, max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS):
        """Initialize the RequestQueue with specified concurrency and rate limits.

        Args:
            max_concurrent_requests (int, optional): Maximum number of concurrent requests.
                Defaults to DEFAULT_MAX_CONCURRENT_REQUESTS.
        """
        self.queues = {
            "search": queue.PriorityQueue(),
            "profile": queue.PriorityQueue(),
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.lock = threading.Lock()
        self.active_requests = 0
        self.counter = itertools.count()  # Unique sequence count

        # Rate limiting attributes
        self.requests_per_second = DEFAULT_API_REQUESTS_PER_SECOND
        self.last_request_time = time.time()
        self.rate_limit_lock = threading.Lock()

        # Posts saver
        self.saver = PostSaver(storage_path=POSTS_STORAGE_PATH)

        logger.debug(
            f"Initialized RequestQueue with max_concurrent_requests={max_concurrent_requests}, "
            f"rate_limit={self.requests_per_second} RPS"
        )

    def add_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        priority: int = DEFAULT_PRIORITY,
    ):
        """Add a new request to the specified queue with given priority.

        Args:
            request_type (str): Type of request ('search' or 'profile').
            request_data (Dict[str, Any]): Request payload data.
                For search: {'query': 'search_term'}
                For profile: {'username': 'twitter_username'}
            priority (int, optional): Priority level (lower number = higher priority).
                Defaults to DEFAULT_PRIORITY (100).

        Example:
            >>> # Search request example
            >>> rq.add_request(
            ...     request_type='search',
            ...     request_data={'query': '#AI AND #ML'},
            ...     priority=1
            ... )
            >>>
            >>> # Profile request example
            >>> rq.add_request(
            ...     request_type='profile',
            ...     request_data={'username': 'naval'},
            ...     priority=2
            ... )
        """
        if request_type in self.queues:
            count = next(self.counter)
            self.queues[request_type].put((priority, count, request_data))
            logger.info(
                f"Request added to {
                        request_type} queue with priority {priority}"
            )

    async def excecute_request(self, request_type: str, request_data: Dict[str, Any]):
        response = self._handle_request(request_type, request_data, True)
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

    def process_requests(self):
        """Continuously process requests from all queues in a separate thread.

        This method runs in an infinite loop, checking each queue for pending requests
        and processing them if the concurrent request limit hasn't been reached.
        Requests are processed in priority order and are rate-limited according to
        the requests_per_second setting.
        """
        logger.debug("Starting to process requests")
        while True:
            for request_type, q in self.queues.items():
                if (
                    not q.empty()
                    and self.active_requests < self.max_concurrent_requests
                ):
                    priority, count, request_data = q.get()
                    logger.debug(
                        f"Processing {request_type} request with priority {priority}"
                    )
                    threading.Thread(
                        target=self._handle_request,
                        args=(request_type, request_data),
                        daemon=THREAD_DAEMON,
                    ).start()

    def _handle_request(
        self, request_type: str, request_data: Dict[str, Any], quick_return=False
    ):
        """Process a single request with error handling, retry mechanism, and rate limiting.

        Args:
            request_type (str): Type of request being processed.
            request_data (Dict[str, Any]): Request payload data.

        Note:
            This method enforces rate limiting before making the actual API request.
        """
        with self.lock:
            self.active_requests += 1
            logger.debug(
                f"Active requests increased to {
                         self.active_requests}"
            )

        try:
            self._wait_for_rate_limit()  # Apply rate limiting before making request

            if request_type == "profile":
                response = get_x_profile(username=request_data["username"])
            elif request_type == "search":
                response = search_x(query=request_data["query"])
            else:
                raise ValueError(f"Unknown request type: {request_type}")

            if quick_return:
                return response

            if response["data"] is not None:
                logger.info(f"Processed {request_type} request: {response}")

                metadata = {
                    "uid": request_data["metadata"].UID,
                    "user_id": request_data["metadata"].UserID,
                    "subnet_id": request_data["metadata"].SubnetID,
                    "query": request_data["query"],
                    "count": len(response),
                    "created_at": int(time.time()),
                }

                self.saver.save_post(response, metadata)
                return response, metadata

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self._retry_request(request_type, request_data)
        finally:
            with self.lock:
                self.active_requests -= 1
                logger.debug(
                    f"Active requests decreased to {
                             self.active_requests}"
                )

    def _retry_request(
        self,
        request_type: str,
        request_data: Dict[str, Any],
        retries: int = DEFAULT_RETRIES,
    ):
        """Retry failed requests with exponential backoff.

        Args:
            request_type (str): Type of request to retry.
            request_data (Dict[str, Any]): Request payload data.
            retries (int, optional): Maximum number of retry attempts.
                Defaults to DEFAULT_RETRIES.

        Note:
            Uses BACKOFF_BASE_SLEEP for the exponential backoff calculation.
            Delay = BACKOFF_BASE_SLEEP * (2 ^ attempt)
        """
        for attempt in range(retries):
            try:
                logger.warning(
                    f"Retrying {request_type} request: {
                               request_data}, attempt {attempt + 1}"
                )
                # Exponential backoff
                time.sleep(BACKOFF_BASE_SLEEP * (2**attempt))
                return
            except Exception as e:
                logger.error(f"Retry failed: {e}")
        logger.error(
            f"Request failed after {
                     retries} attempts: {request_data}"
        )

    def start(self):
        """Start the request processing thread as a daemon thread.

        Note:
            Thread daemon status is controlled by THREAD_DAEMON constant.
            The processing thread will handle requests according to their priority
            and respect both concurrency limits and rate limiting settings.

        Example:
            >>> rq = RequestQueue(max_concurrent_requests=5)
            >>> rq.start()  # Starts processing thread
            >>>
            >>> # Add requests after starting the queue
            >>> rq.add_request('search', {'query': '#Bitcoin'}, priority=1)
            >>> rq.add_request('profile', {'username': 'vitalikbuterin'}, priority=2)
        """
        logger.debug("Starting request processing thread")
        self.thread = threading.Thread(
            target=self.process_requests, daemon=THREAD_DAEMON
        )
        self.thread.start()

    def stop(self):
        """Stop the request processing thread.

        This method will signal the processing thread to stop and wait for it to finish.
        It ensures that all active requests are completed before the thread is terminated.
        """
        logger.debug("Stopping request processing thread")
        self.active_requests = 0  # Reset active requests counter
        self.thread.join()  # Wait for the thread to finish

    def clean(self):
        """Clean up the request queue and reset its state.

        This method is responsible for cleaning up the request queue by stopping
        the processing thread and resetting the queues to their initial state.
        It ensures that all resources are properly released and the queue is
        ready for a fresh start if needed.

        Note:
            This method should be called when the queue is no longer needed or
            before reinitializing it to prevent resource leaks.
        """
        self.stop()
        self.queues = None


if __name__ == "__main__":

    rq = RequestQueue()
    rq.start()
    rq.add_request("search", {"query": "#Bitcoin"}, priority=1)
    rq.add_request("profile", {"username": "elonmusk"}, priority=2)
    time.sleep(10)  # Keep the main thread alive to allow processing

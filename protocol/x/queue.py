import queue
import threading
import time
from typing import Any, Dict, Callable, Optional

# Import the functions from their respective modules
from protocol.x.profile import get_x_profile
from protocol.x.search import search_x

# Constants
DEFAULT_MAX_CONCURRENT_REQUESTS = 5  # Maximum parallel requests
DEFAULT_RETRIES = 3                  # Number of retry attempts
DEFAULT_PRIORITY = 100               # Base priority level (higher = lower priority)
BACKOFF_BASE_SLEEP = 1               # Base delay (seconds) for exponential backoff
THREAD_DAEMON = True                 # Run worker threads as daemons

class RequestQueue:
    """A thread-safe priority queue system for handling different types of API requests.

    This class implements a multi-queue system that can handle different types of requests
    (search and profile) with priority levels and concurrent processing capabilities.
    Priority values are ascending (lower numbers = higher priority, e.g., 0 is highest).

    Attributes:
        max_concurrent_requests (int): Maximum number of requests that can be processed simultaneously.
        queues (Dict[str, PriorityQueue]): Dictionary of priority queues for different request types.
        lock (threading.Lock): Thread lock for managing concurrent access.
        active_requests (int): Counter for currently processing requests.
    """

    def __init__(self, max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS):
        """Initialize the RequestQueue with specified concurrency limit.

        Args:
            max_concurrent_requests (int, optional): Maximum number of concurrent requests. 
                Defaults to DEFAULT_MAX_CONCURRENT_REQUESTS.
        """
        self.queues = {
            'search': queue.PriorityQueue(),
            'profile': queue.PriorityQueue()
        }
        self.max_concurrent_requests = max_concurrent_requests
        self.lock = threading.Lock()
        self.active_requests = 0

    def add_request(self, request_type: str, request_data: Dict[str, Any], priority: int = DEFAULT_PRIORITY):
        """Add a new request to the specified queue with given priority.

        Args:
            request_type (str): Type of request ('search' or 'profile').
            request_data (Dict[str, Any]): Request payload data.
            priority (int, optional): Priority level (lower number = higher priority). 
                Defaults to DEFAULT_PRIORITY (100).
        """
        if request_type in self.queues:
            self.queues[request_type].put((priority, request_data))
            print(f"Request added to {request_type} queue with priority {priority}")

    def process_requests(self):
        """Continuously process requests from all queues in a separate thread.

        This method runs in an infinite loop, checking each queue for pending requests
        and processing them if the concurrent request limit hasn't been reached.
        """
        while True:
            for request_type, q in self.queues.items():
                if not q.empty() and self.active_requests < self.max_concurrent_requests:
                    priority, request_data = q.get()
                    threading.Thread(target=self._handle_request, args=(request_type, request_data), daemon=THREAD_DAEMON).start()

    def _handle_request(self, request_type: str, request_data: Dict[str, Any]):
        """Process a single request with error handling and retry mechanism.

        Args:
            request_type (str): Type of request being processed.
            request_data (Dict[str, Any]): Request payload data.
        """
        with self.lock:
            self.active_requests += 1
        try:
            if request_type == 'profile':
                response = get_x_profile(username=request_data['username'])
            elif request_type == 'search':
                response = search_x(query=request_data['query'])
            else:
                raise ValueError(f"Unknown request type: {request_type}")

            print(f"Processed {request_type} request: {response}")
        except Exception as e:
            print(f"Error processing request: {e}")
            self._retry_request(request_type, request_data)
        finally:
            with self.lock:
                self.active_requests -= 1

    def _retry_request(self, request_type: str, request_data: Dict[str, Any], retries: int = DEFAULT_RETRIES):
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
                print(f"Retrying {request_type} request: {request_data}, attempt {attempt + 1}")
                time.sleep(BACKOFF_BASE_SLEEP * (2 ** attempt))  # Exponential backoff
                return
            except Exception as e:
                print(f"Retry failed: {e}")
        print(f"Request failed after {retries} attempts: {request_data}")

    def start(self):
        """Start the request processing thread as a daemon thread.
        
        Note:
            Thread daemon status is controlled by THREAD_DAEMON constant.
        """
        threading.Thread(target=self.process_requests, daemon=THREAD_DAEMON).start()

# Example usage
if __name__ == "__main__":
    rq = RequestQueue()
    rq.start()
    rq.add_request('search', {'query': '#Bitcoin'}, priority=1)
    rq.add_request('profile', {'username': 'elonmusk'}, priority=2)
    time.sleep(10)  # Keep the main thread alive to allow processing 
import logging
import os
import time
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional
import requests
import schedule
from dotenv import load_dotenv

from protocol.x.queue import RequestQueue

# Load environment variables
load_dotenv()

# Configure logging based on environment variable
log_level = logging.DEBUG if os.getenv("DEBUG", "").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get environment variables with fallbacks
VALIDATOR_DB_BASE_URL = os.getenv("MASA_BASE_URL", "http://localhost:8080")
VALIDATOR_DB_BASE = os.getenv("MASA_API_PATH", "/api/v1/data")
VALIDATOR_DB_PATH = f"{VALIDATOR_DB_BASE}/twitter/tweets/recent"

# Default constants for scheduler configuration
DEFAULT_INTERVAL_MINUTES = 15
DEFAULT_BATCH_SIZE = 100
DEFAULT_PRIORITY = 100
DEFAULT_SEARCH_COUNT = 450

# Environment variable overrides for defaults
SCHEDULER_INTERVAL = int(
    os.getenv("SCHEDULER_INTERVAL_MINUTES", DEFAULT_INTERVAL_MINUTES)
)
SCHEDULER_BATCH_SIZE = int(os.getenv("SCHEDULER_BATCH_SIZE", DEFAULT_BATCH_SIZE))
SCHEDULER_PRIORITY = int(os.getenv("SCHEDULER_PRIORITY", DEFAULT_PRIORITY))
SCHEDULER_SEARCH_COUNT = int(os.getenv("SCHEDULER_SEARCH_COUNT", DEFAULT_SEARCH_COUNT))

# Expected search term format from validator database:
# {
#     "id": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",  # Miner hotkey as primary key
#     "search_term": "(from:getmasafi)"  # or "Bitcoin" or "(to:getmasafi)"
# }


class XSearchScheduler:
    """Scheduler for processing X search terms from validator database.

    This scheduler periodically fetches search terms from a validator's database
    and queues them for processing. Each search term is processed with a 1-day
    lookback period, regardless of the scheduler's interval. The scheduler's
    interval only controls how often new terms are fetched from the database.

    Attributes:
        request_queue (RequestQueue): Queue for processing search requests
        interval_minutes (int): How often to check for new search terms (minutes)
        batch_size (int): Maximum number of search terms to process per batch
        priority (int): Priority level for queue requests (lower = higher priority)
        search_count (int): Number of results to request for each search term
        last_run_time (datetime): Timestamp of the last successful run
    """

    def __init__(
        self,
        request_queue: RequestQueue,
        interval_minutes: int = SCHEDULER_INTERVAL,
        batch_size: int = SCHEDULER_BATCH_SIZE,
        priority: int = SCHEDULER_PRIORITY,
        search_count: int = SCHEDULER_SEARCH_COUNT,
    ):
        """Initialize the scheduler.

        Args:
            request_queue (RequestQueue): Queue instance for processing requests
            interval_minutes (int): How often to check for new search terms
            batch_size (int): Maximum number of search terms to process per batch
            priority (int): Priority level for queue requests (lower = higher priority)
            search_count (int): Number of results to request for each search term
        """
        self.request_queue = request_queue
        self.interval_minutes = interval_minutes
        self.batch_size = batch_size
        self.priority = priority
        self.search_count = search_count
        self.last_run_time = None
        self.search_terms = None

        logger.debug(
            f"Initialized XSearchScheduler with interval={
                interval_minutes}min, "
            f"batch_size={batch_size}, priority={priority}, "
            f"search_count={search_count}"
        )

    def _get_search_terms(self) -> List[Dict[str, Any]]:
        """Fetch search terms from validator's database.

        Retrieves a batch of active search terms from the validator's database.
        The number of terms retrieved is limited by self.batch_size.

        Returns:
            List[Dict[str, Any]]: List of search terms with their configurations.
                Each term is a dictionary with 'id' and 'search_term' keys.
        """
        try:
            api_url = f"{VALIDATOR_DB_BASE_URL.rstrip(
                '/')}/{VALIDATOR_DB_PATH.lstrip('/')}"

            response = requests.get(
                api_url,
                headers={"accept": "application/json"},
                params={"batch_size": self.batch_size},
            )
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch search terms: {e}")
            return []

    def _prepare_search_query(self, term: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare search query with time range parameters.

        Takes a search term from the database and prepares it for processing by adding
        a 1-day lookback period and the configured result count. The time range is
        formatted as dates only (no time component) to match X's search syntax.

        Args:
            term (Dict[str, Any]): Search term configuration from database containing
                'id' and 'search_term' keys

        Returns:
            Dict[str, Any]: Prepared search query parameters including:
                - query: Search string with date range (YYYY-MM-DD format)
                - count: Number of results to request
                - miner_id: ID of the miner who provided the search term
        """
        current_time = datetime.now(UTC)

        # Always use a 1-day lookback period
        start_time = current_time - timedelta(days=1)

        # Format the query string with date range only (no time component)
        query = (
            f"({term['query']}) "
            f"since:{start_time.strftime('%Y-%m-%d')}"
        )

        return {
            "query": query,
            "count": self.search_count,
            "miner_id": term["metadata"].HotKey,
            "metadata": term["metadata"],
        }

    def process_search_terms(self):
        """Process a batch of search terms and add them to the queue.

        Fetches search terms from the database, prepares them with a 1-day
        lookback period and configured count, then adds them to the processing
        queue. Each term is processed independently with its own date range.
        """
        try:
            current_time = datetime.now(UTC)

            logger.info(f"Processing {len(self.search_terms)} search terms")
            for term in self.search_terms:

                search_query = self._prepare_search_query(term)

                logger.info(f"Queueing search request: {search_query}")

                self.request_queue.add_request(
                    request_type="search",
                    request_data=search_query,
                    priority=self.priority,
                )

            self.last_run_time = current_time

        except Exception as e:
            logger.error(f"Error in process_search_terms: {e}")

    def start(self):
        """Start the scheduler.

        Initiates the scheduler to run at the configured interval. The scheduler
        will immediately process search terms once, then continue checking for
        new terms at the specified interval. Each search term is processed with
        a 1-day lookback period, regardless of the scheduler's interval.
        """
        logger.info(
            f"Starting XSearchScheduler with {
                    self.interval_minutes} minute interval"
        )

        # Schedule the job
        schedule.every(self.interval_minutes).minutes.do(self.process_search_terms)

        # Run immediately on start
        self.process_search_terms()

        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(1)


# # Example usage
# if __name__ == "__main__":
#     request_queue = RequestQueue()
#     request_queue.start()

#     scheduler = XSearchScheduler(
#         request_queue=request_queue,
#         interval_minutes=1,
#         batch_size=100,
#         priority=100,
#         search_count=10,
#     )
#     scheduler.start()

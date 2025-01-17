"""
Protocol API Posts Getter Module

This module provides functionality to fetch posts from the Protocol API service within
specified time ranges. It handles authentication, error handling, and proper API versioning
for subnet post retrieval operations.

Key Components:
    - PostsGetter: Main class for fetching posts with configurable date ranges
    - PostsAPIError: Custom exception for handling API-specific errors

Environment Variables:
    - API_KEY: Authentication token for the Protocol API (optional)
    - API_URL: Base URL for the API (defaults to https://test.protocol-api.masa.ai)

Usage Example:
    ```python
    from datetime import datetime, UTC
    
    # Initialize with default 7-day lookback
    getter = PostsGetter(netuid=59)
    
    # Or specify custom date range
    getter = PostsGetter(
        netuid=59,
        start_date=datetime(2024, 1, 1, tzinfo=UTC),
        end_date=datetime(2024, 1, 7, tzinfo=UTC)
    )
    
    # Fetch posts asynchronously
    posts = await getter.get()
    ```

Note:
    All timestamps are handled in UTC timezone to ensure consistency
    across different environments and time zones.
"""

from dataclasses import dataclass
from typing import List, Any, Optional
from datetime import datetime, UTC, timedelta
from fiber.logging_utils import get_logger
import httpx
import os

logger = get_logger(__name__)

# Constants
DEFAULT_DAYS_LOOKBACK = 7
DEFAULT_API_URL = "https://test.protocol-api.masa.ai"
API_VERSION = "v1.0.0"
SUBNET_API_PATH = "subnet59"


class PostsAPIError(Exception):
    """
    PostsAPIError represents errors that occur during Posts API operations.
    
    Attributes:
        status_code: Optional HTTP status code from the failed request
        response_body: Optional response body from the failed request
        message: Descriptive error message
    """
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Posts API Error: {message} " + 
                        (f"(Status: {status_code})" if status_code else "") +
                        (f" - Response: {response_body}" if response_body else ""))


@dataclass
class PostsGetter:
    """
    PostsGetter handles fetching posts from the Protocol API within a specified date range.
    
    If no date range is provided, it defaults to fetching posts from the last 7 days.
    The class handles authentication and proper API versioning.
    
    Attributes:
        netuid: Network user identifier for the subnet
        start_date: Optional start date for post fetching (defaults to 7 days ago)
        end_date: Optional end date for post fetching (defaults to current time)
    
    Example:
        getter = PostsGetter(netuid=1)
        posts = await getter.get()
    """
    netuid: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.start_date = self.start_date or (datetime.now(UTC) - timedelta(days=DEFAULT_DAYS_LOOKBACK))
        self.end_date = self.end_date or datetime.now(UTC)
        
        self.start_timestamp = int(self.start_date.timestamp())
        self.end_timestamp = int(self.end_date.timestamp())

        self._setup_client()

    def _setup_client(self) -> None:
        """
        _setup_client initializes the HTTP client with authentication headers.
        
        Uses API_KEY from environment variables if available. The client is configured
        with proper authentication headers and base URL settings.
        """
        self.api_key = os.getenv("API_KEY")
        self.api_url = os.getenv("API_URL", DEFAULT_API_URL)
        
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug(f"Initializing PostsGetter with{'out' if not self.api_key else ''} API authentication")
        
        self.httpx_client = httpx.AsyncClient(
            headers=headers
        )

    async def get(self) -> List[Any]:
        """
        get fetches posts for the configured date range.
        
        Returns:
            List[Any]: List of posts within the specified date range
            
        Note:
            The posts are fetched asynchronously using httpx client.
        """
        posts = await self._fetch_posts()
        logger.info(
            f"Loaded {len(posts)} posts between {datetime.fromtimestamp(self.start_timestamp, UTC)} "
            f"and {datetime.fromtimestamp(self.end_timestamp, UTC)}"
        )
        return posts

    async def _fetch_posts(self) -> List[Any]:
        """
        _fetch_posts performs the actual HTTP request to fetch posts.
        
        Returns:
            List[Any]: List of posts from the API response
            
        Raises:
            PostsAPIError: When the API request fails with non-200 status code
            
        Note:
            This method handles various error cases and logs appropriate messages.
            On error, it returns an empty list instead of raising exceptions.
        """
        try:
            response = await self.httpx_client.get(
                f"{self.api_url}/{API_VERSION}/{SUBNET_API_PATH}/miners/posts",
                params={"since": self.start_timestamp, "until": self.end_timestamp}
            )
            
            if response.status_code == 200:
                posts = response.json().get("posts", [])
                logger.info(f"Successfully fetched {len(posts)} posts from API")
                return posts
                
            raise PostsAPIError(
                message="Failed to fetch posts",
                status_code=response.status_code,
                response_body=response.text
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching posts: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error while fetching posts: {str(e)}")
            return []

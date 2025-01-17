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
    """Custom exception for Posts API related errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Posts API Error: {message} " + 
                        (f"(Status: {status_code})" if status_code else "") +
                        (f" - Response: {response_body}" if response_body else ""))


@dataclass
class PostsGetter:
    """
    Fetches posts from the API within a specified date range.
    If no date range is provided, defaults to the last 7 days.
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
        """Sets up the HTTP client with appropriate headers"""
        self.api_key = os.getenv("API_KEY")
        self.api_url = os.getenv("API_URL", DEFAULT_API_URL)
        
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug(f"Initializing PostsGetter with{'out' if not self.api_key else ''} API authentication")
        
        self.httpx_client = httpx.AsyncClient(
            headers=headers
        )

    async def get(self) -> List[Any]:
        """Fetches and returns posts for the configured date range"""
        posts = await self._fetch_posts()
        logger.info(
            f"Loaded {len(posts)} posts between {datetime.fromtimestamp(self.start_timestamp, UTC)} "
            f"and {datetime.fromtimestamp(self.end_timestamp, UTC)}"
        )
        return posts

    async def _fetch_posts(self) -> List[Any]:
        """Fetches posts from the API within the specified date range"""
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

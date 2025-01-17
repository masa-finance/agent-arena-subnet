from typing import List, Any
from datetime import datetime, UTC
from fiber.logging_utils import get_logger
import httpx
import os

logger = get_logger(__name__)


class PostsGetter:
    def __init__(self, netuid: int, start_date: datetime | None = None, end_date: datetime | None = None):
        self.netuid = netuid
        
        # Default to last 7 days if no dates provided
        if start_date is None:
            a_week_ago_in_seconds = 7 * 24 * 60 * 60
            start_date = datetime.now(UTC) - datetime.timedelta(seconds=a_week_ago_in_seconds)
        if end_date is None:
            end_date = datetime.now(UTC)
            
        self.start_timestamp = int(start_date.timestamp())
        self.end_timestamp = int(end_date.timestamp())

        self.api_key = os.getenv("API_KEY", None)
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url, headers={"Authorization": f"Bearer {self.api_key}"}
        )

    async def get(self) -> List[Any]:
        posts = await self.fetch_posts_from_api(self.start_timestamp, self.end_timestamp)
        logger.info(f"Loaded {len(posts)} posts between {datetime.fromtimestamp(self.start_timestamp, UTC)} and {datetime.fromtimestamp(self.end_timestamp, UTC)}")
        return posts

    async def fetch_posts_from_api(self, start_timestamp: int, end_timestamp: int) -> List[Any]:
        """Fetch posts from the API within the specified date range"""
        try:
            response = await self.httpx_client.get(
                f"{self.api_url}/v1.0.0/subnet59/miners/posts",
                params={"since": start_timestamp, "until": end_timestamp}
            )
            if response.status_code == 200:
                posts_data = response.json()
                posts = posts_data.get("posts", [])
                logger.info(f"Successfully fetched {len(posts)} posts from API")
                return posts
            else:
                logger.error(
                    f"Failed to fetch posts, status code: {response.status_code}, message: {response.text}"
                )
                return []
        except Exception as e:
            logger.error(f"Exception occurred while fetching posts: {str(e)}")
            return []  # Added explicit return for exception case

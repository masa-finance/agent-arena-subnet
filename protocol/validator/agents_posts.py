from typing import List, Any
from datetime import datetime, UTC
from fiber.logging_utils import get_logger
import httpx
import os

logger = get_logger(__name__)


class AgentsPosts:
    def __init__(self, netuid: int):
        self.netuid = netuid
        self.posts = []

        self.since = int(datetime.now(UTC).timestamp()) - 604800

        self.api_key = os.getenv("API_KEY", None)
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url, headers={"Authorization": f"Bearer {self.api_key}"}
        )

    async def get(self) -> List[Any]:

        posts = await self.fetch_posts_from_api(self.since)
        logger.info(f"Loaded {len(posts)} posts")
        self.posts = posts
        return self.posts

    async def fetch_posts_from_api(self, since) -> None:
        """Fetch posts from the API and update self.posts"""
        try:
            response = await self.httpx_client.get(
                f"{self.api_url}/v1.0.0/subnet59/miners/posts?since={since}"
            )
            if response.status_code == 200:
                posts_data = response.json()
                self.posts = posts_data.get("posts", [])
                logger.info("Successfully fetched and updated posts from API.")
            else:
                logger.error(
                    f"Failed to fetch posts, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred while fetching posts: {str(e)}")

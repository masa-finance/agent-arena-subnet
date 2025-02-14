from typing import List, Any, Optional
from datetime import datetime, UTC
from fiber.logging_utils import get_logger
import httpx
import os
from interfaces.types import Tweet

logger = get_logger(__name__)


class PostsGetter:
    def __init__(self, netuid: int):
        self.netuid = netuid
        a_week_ago_in_seconds = 7 * 24 * 60 * 60
        self.since = int(datetime.now(UTC).timestamp()) - a_week_ago_in_seconds

        self.api_key = os.getenv("API_KEY", None)
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=120,
        )

    async def get(self) -> List[Optional[Tweet]]:
        posts = await self.fetch_posts_from_api(self.since)
        return posts

    async def fetch_posts_from_api(self, since) -> List[Optional[Tweet]]:
        """Fetch posts from the API and update self.posts"""
        posts = []
        try:
            response = await self.httpx_client.get(
                f"{self.api_url}/v1.0.0/subnet59/miners/posts?since={since}"
            )
            if response.status_code == 200:
                posts_data = dict(response.json())
                posts = posts_data.get("posts", [])
                logger.info(f"Successfully fetched {len(posts)} posts from API")
            else:
                logger.error(
                    f"Failed to fetch posts, status code: {response.status_code}, message: {response.text}"
                )
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected exception occurred: {str(e)}")
        finally:
            return posts

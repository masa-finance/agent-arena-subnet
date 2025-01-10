from typing import List, Any
from datetime import datetime, UTC
from fiber.logging_utils import get_logger
from protocol.data_processing.post_loader import LoadPosts

logger = get_logger(__name__)


class ValidatorScoring:
    def __init__(self, netuid: int):
        self.netuid = netuid
        self.posts_loader = LoadPosts()
        self.scored_posts = []

    def score_posts(self) -> List[Any]:
        posts = self.posts_loader.load_posts(
            subnet_id=self.netuid,
            timestamp_range=(
                int(datetime.now(UTC).timestamp()) - 604800,  # 7 days
                int(datetime.now(UTC).timestamp()),
            ),
        )
        logger.info(f"Loaded {len(posts)} posts")
        self.scored_posts = posts
        return self.scored_posts

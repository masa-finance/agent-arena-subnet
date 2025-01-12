import json
import fcntl
from typing import List, Dict, Any, Optional
from pathlib import Path
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

class LoadPosts:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent.parent
        self.data_path = self.root_dir / "data" / "posts.json"
        self.backup_path = self.data_path.with_suffix('.json.backup')

    def _safe_load_json(self) -> List[Dict]:
        """Safely load JSON with fallback to backup file."""
        with open(self.data_path, "r") as file:
            # Acquire shared lock for reading
            fcntl.flock(file.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(file)
            except json.JSONDecodeError:
                logger.error("Corrupted JSON detected, attempting to restore from backup")
                if self.backup_path.exists():
                    with open(self.backup_path, "r") as backup_file:
                        return json.load(backup_file)
                return []
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    def load_posts(
        self,
        uid: Optional[str] = None,
        user_id: Optional[str] = None,
        subnet_id: Optional[str] = None,
        timestamp_range: Optional[tuple[int, int]] = None,
        created_at_range: Optional[tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Loads and filters posts based on provided parameters.
        All parameters are optional - if none are provided, returns all posts.

        Args:
            uid (str, optional): Filter by specific UID
            user_id (str, optional): Filter by specific user ID
            subnet_id (str, optional): Filter by specific subnet ID
            timestamp_range (tuple[int, int], optional): Filter by post timestamp range (start, end)
            created_at_range (tuple[int, int], optional): Filter by search request created_at range (start, end)

        Returns:
            List[Dict[str, Any]]: Filtered list of posts/tweets

        Raises:
            FileNotFoundError: If posts.json doesn't exist
            json.JSONDecodeError: If JSON is malformed
        """
        try:
            posts = self._safe_load_json()

            filtered_posts = []
            for post in posts:
                # Check if post matches all provided filters
                matches = True

                if uid and post["uid"] != uid:
                    matches = False

                if user_id and post["user_id"] != user_id:
                    matches = False

                if subnet_id and post["subnet_id"] != subnet_id:
                    matches = False

                if timestamp_range:
                    start_time, end_time = timestamp_range
                    # Check if any tweet in the post falls within the timestamp range
                    tweet_matches = False
                    for tweet_data in post["tweets"]:
                        tweet_timestamp = tweet_data["Tweet"]["Timestamp"]
                        if start_time <= tweet_timestamp <= end_time:
                            tweet_matches = True
                            break
                    if not tweet_matches:
                        matches = False

                if created_at_range:
                    start_time, end_time = created_at_range
                    if not (start_time <= post["created_at"] <= end_time):
                        matches = False

                if matches:
                    filtered_posts.append(post)

            return filtered_posts

        except FileNotFoundError:
            logger.error(f"Posts file not found at: {self.data_path}")
            return []
        except Exception as e:
            logger.error(f"Error loading posts: {str(e)}")
            return []


# Example usage
if __name__ == "__main__":
    posts_loader = LoadPosts()
    try:
        # Load all posts (no filters)
        all_posts = posts_loader.load_posts()
        print(f"All posts: {len(all_posts)}")

        # Load with single filter
        uid_posts = posts_loader.load_posts(uid="1")
        print(f"Posts for UID 1: {len(uid_posts)}")

        # Load with multiple filters
        filtered_posts = posts_loader.load_posts(
            user_id="1470086780",
            subnet_id="59",
            timestamp_range=(1725519100, 1725519200),
        )
        print(f"Posts with multiple filters: {len(filtered_posts)}")

    except Exception as e:
        print(f"Error: {str(e)}")

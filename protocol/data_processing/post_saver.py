import json
from typing import TypedDict
from pathlib import Path
import fcntl
import tempfile
import shutil
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


class Metadata(TypedDict):
    """Type definition for post metadata.

    Attributes:
        uid (str): Unique identifier for the post
        user_id (str): User identifier
        subnet_id (str): Subnet identifier
        query (str): Search query used
        count (int): Number of items
        created_at (int): Unix timestamp of creation
    """
    uid: str
    user_id: str
    subnet_id: str
    query: str
    count: int
    created_at: int


class PostSaver:
    """Handles saving and managing tweet posts to JSON storage.

    This class provides functionality to save tweet data while handling duplicates
    and managing file storage operations.

    Attributes:
        storage_path (Path): Path to the JSON storage file
    """

    def __init__(self, storage_path: str = 'data/posts.json'):
        """Initialize PostSaver with storage configuration.

        Args:
            storage_path (str): Path to JSON storage file. Defaults to 'data/posts.json'
        """
        self.storage_path = Path(storage_path)
        self.backup_path = self.storage_path.with_suffix('.json.backup')
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize empty storage file if it doesn't exist
        if not self.storage_path.exists():
            self._atomic_write([])

    def _atomic_write(self, data: list) -> None:
        """Atomically write data to the storage file using a temporary file."""
        # Create a temporary file in the same directory
        with tempfile.NamedTemporaryFile(mode='w', dir=str(self.storage_path.parent),
                                       delete=False, suffix='.tmp') as tmp_file:
            # Write data to temporary file
            json.dump(data, tmp_file, indent=4)
            tmp_file.flush()  # Ensure all data is written
            
            # Create backup of current file if it exists
            if self.storage_path.exists():
                shutil.copy2(self.storage_path, self.backup_path)
            
            # Atomic rename of temporary file to target file
            shutil.move(tmp_file.name, self.storage_path)

    def save_post(self, response, metadata: Metadata) -> None:
        """Save tweet posts to a JSON file while handling duplicates.

        This function processes tweet data and saves it to the configured JSON file. 
        It checks for duplicate tweets based on Tweet IDs and only saves new, unique tweets.

        Args:
            response: The response object containing tweet data
                Expected format: {"data": [{"Tweet": {"ID": "...", ...}}, ...]}
            metadata (Metadata): TypedDict containing post metadata including uid,
                user_id, subnet_id, query, count, and created_at

        Raises:
            FileNotFoundError: If storage file cannot be created/accessed
            json.JSONDecodeError: If existing JSON file is malformed
        """

        if response is None:
            return

        # Use file locking to prevent concurrent access
        with open(self.storage_path, 'r+') as file:
            try:
                # Acquire exclusive lock
                fcntl.flock(file.fileno(), fcntl.LOCK_EX)
                
                try:
                    existing_posts = json.load(file)
                except json.JSONDecodeError:
                    logger.error("Corrupted JSON detected, attempting to restore from backup")
                    if self.backup_path.exists():
                        existing_posts = json.loads(self.backup_path.read_text())
                    else:
                        existing_posts = []

                # Prepare new post data
                new_post = {
                    **metadata,
                    "tweets": response.get("data", [])
                }

                # Check for duplication based on tweet 'ID'
                existing_tweet_ids = {
                    tweet['Tweet']['ID']
                    for post in existing_posts
                    for tweet in post['tweets']
                }
                new_tweets = [
                    tweet for tweet in new_post['tweets']
                    if tweet['Tweet']['ID'] not in existing_tweet_ids
                ]

                if new_tweets:
                    new_post['tweets'] = new_tweets
                    existing_posts.append(new_post)
                    self._atomic_write(existing_posts)
                    logger.info(f"Stored posts for {metadata.get('query')}")
                else:
                    logger.info("All tweets are duplicates, not adding to storage")

            finally:
                # Release lock
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)

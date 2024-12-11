import json
from typing import TypedDict
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


class Metadata(TypedDict):
    uid: str
    user_id: str
    subnet_id: str
    query: str
    count: int
    created_at: int


def save_post(response, metadata: Metadata):

    # Load existing posts from data/posts.json
    try:
        with open('data/posts.json', 'r', encoding='utf-8') as file:
            existing_posts = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_posts = []

    # Prepare new post data
    new_post = {
        **metadata,
        "tweets": response.get("data", [])
    }

    # Check for duplication based on tweet 'ID'
    existing_tweet_ids = {tweet['Tweet']['ID']
                          for post in existing_posts for tweet in post['tweets']}
    new_tweets = [tweet for tweet in new_post['tweets']
                  if tweet['Tweet']['ID'] not in existing_tweet_ids]

    if new_tweets:
        new_post['tweets'] = new_tweets
        existing_posts.append(new_post)

        # Save updated posts back to data/posts.json
        with open('data/posts.json', 'w', encoding='utf-8') as file:
            json.dump(existing_posts, file, indent=4)

        logger.info(f"Stored posts for {metadata.get("query")}")

    else:
        logger.info("All tweets are duplicates, not adding to data/posts.json")

from fiber.logging_utils import get_logger
from masa_ai.tools.validator import TweetValidator
from datetime import datetime
from interfaces.types import VerifiedTweet


logger = get_logger(__name__)


async def verify_tweet(id: str, hotkey: str) -> tuple[VerifiedTweet, str]:
    """Fetch tweet from Twitter API"""
    try:
        logger.info(f"Verifying tweet: {id}")
        result = TweetValidator().fetch_tweet(id)

        if not result:
            logger.error(f"Could not fetch tweet id {id} for node {hotkey}")
            return False

        tweet_data_result = (
            result.get("data", {}).get("tweetResult", {}).get("result", {})
        )
        created_at = tweet_data_result.get("legacy", {}).get("created_at")
        tweet_id = tweet_data_result.get("rest_id")
        user = (
            tweet_data_result.get("core", {}).get("user_results", {}).get("result", {})
        )
        screen_name = user.get("legacy", {}).get("screen_name")
        user_id = user.get("rest_id")
        full_text = tweet_data_result.get("legacy", {}).get("full_text")

        logger.info(
            f"Got tweet result: {
                    tweet_id} - {screen_name} **** {full_text}"
        )

        if not isinstance(screen_name, str) or not isinstance(full_text, str):
            msg = "Invalid tweet data: screen_name or full_text is not a string"
            logger.error(msg)
            raise ValueError(msg)

        # Ensure that the hotkey (full_text) is registered on the metagraph and matches the node that returned the tweet ID
        if not hotkey == full_text:
            msg = f"Hotkey {full_text} does not match node hotkey {
                hotkey}"
            logger.error(msg)
            raise ValueError(msg)

        verification_tweet = VerifiedTweet(
            tweet_id=tweet_id,
            url=f"https://twitter.com/{screen_name}/status/{tweet_id}",
            timestamp=datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            full_text=full_text,
        )
        return verification_tweet, user_id
    except Exception as e:
        logger.error(f"Failed to register agent: {str(e)}")
        return False

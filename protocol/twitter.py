import tweepy
from typing import Optional
from protocol.base import TwitterMetrics
import time
import logging

logger = logging.getLogger(__name__)

class TwitterService:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        """Initialize Twitter API client"""
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        self.api = tweepy.API(auth)
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

    async def get_user_metrics(self, twitter_handle: str) -> Optional[TwitterMetrics]:
        """Fetch Twitter metrics for a given user"""
        try:
            # Get user info
            user = self.client.get_user(username=twitter_handle)
            if not user.data:
                logger.error(f"User {twitter_handle} not found")
                return None

            user_id = user.data.id

            # Get recent tweets
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=100,
                tweet_fields=['public_metrics']
            )

            if not tweets.data:
                logger.warning(f"No tweets found for {twitter_handle}")
                return TwitterMetrics(
                    impressions=0,
                    likes=0,
                    replies=0,
                    followers=user.data.public_metrics['followers_count'],
                    timestamp=time.time()
                )

            # Calculate metrics
            total_impressions = 0
            total_likes = 0
            total_replies = 0

            for tweet in tweets.data:
                metrics = tweet.public_metrics
                total_impressions += metrics['impression_count']
                total_likes += metrics['like_count']
                total_replies += metrics['reply_count']

            return TwitterMetrics(
                impressions=total_impressions,
                likes=total_likes,
                replies=total_replies,
                followers=user.data.public_metrics['followers_count'],
                timestamp=time.time()
            )

        except Exception as e:
            logger.error(f"Error fetching metrics for {twitter_handle}: {str(e)}")
            return None
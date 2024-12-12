from typing import Dict, Any, List
import math
from datetime import datetime

class PostScorer:
    """
    PostScorer calculates engagement and quality scores for tweets.
    
    This class provides methods to evaluate tweets based on multiple factors including:
    - Engagement metrics (likes, replies, retweets, views)
    - Content quality (media, hashtags, text length)
    - Interaction patterns (conversations, mentions, threading)
    
    The final score is a weighted combination of these components.
    """

    def __init__(self):
        """
        Initialize PostScorer with default weights and normalization factors.
        
        Weights determine the relative importance of each scoring component:
        - engagement: 40%
        - content_quality: 30% 
        - interaction: 30%
        
        Engagement metrics are normalized against typical values to provide consistent scoring.
        """
        # Weights for different scoring components
        self.weights = {
            'engagement': 0.4,
            'content_quality': 0.3,
            'interaction': 0.3
        }
        
        # Engagement metrics normalization factors
        self.engagement_norm = {
            'likes': 100,
            'replies': 50,
            'retweets': 75,
            'views': 1000
        }

    def calculate_engagement_score(self, tweet: Dict[str, Any]) -> float:
        """
        Calculate engagement score based on likes, replies, retweets, and views.
        
        Args:
            tweet (Dict[str, Any]): Tweet data containing engagement metrics
            
        Returns:
            float: Normalized engagement score between 0 and 1
            
        The score is calculated by:
        1. Normalizing each metric against typical values
        2. Applying log transformation to handle viral outliers
        3. Averaging the transformed metrics
        """
        engagement_metrics = {
            'likes': tweet.get('Likes', 0) / self.engagement_norm['likes'],
            'replies': tweet.get('Replies', 0) / self.engagement_norm['replies'],
            'retweets': tweet.get('Retweets', 0) / self.engagement_norm['retweets'],
            'views': tweet.get('Views', 0) / self.engagement_norm['views']
        }
        
        # Apply log transformation to handle viral outliers
        engagement_score = sum(math.log1p(v) for v in engagement_metrics.values()) / len(engagement_metrics)
        return min(1.0, engagement_score)

    def calculate_content_quality_score(self, tweet: Dict[str, Any]) -> float:
        """
        Evaluate content quality based on tweet characteristics.
        
        Args:
            tweet (Dict[str, Any]): Tweet data containing content information
            
        Returns:
            float: Content quality score between 0 and 1
            
        Evaluates:
        - Media richness (photos, videos, GIFs, URLs)
        - Optimal hashtag usage (1-2 hashtags)
        - Text length optimization (60-200 chars)
        """
        content_scores = []
        
        # Score for media richness
        has_media = any([
            tweet.get('Photos'),
            tweet.get('Videos'),
            tweet.get('GIFs'),
            tweet.get('URLs')
        ])
        content_scores.append(0.5 if has_media else 0.0)
        
        # Score for hashtag usage (optimal is 1-2 hashtags)
        hashtags = tweet.get('Hashtags', [])
        hashtag_count = len(hashtags) if hashtags else 0
        hashtag_score = min(hashtag_count / 2.0, 1.0) if hashtag_count <= 2 else 2.0 / hashtag_count
        content_scores.append(hashtag_score)
        
        # Score for text length (optimal range 60-200 chars)
        text_length = len(tweet.get('Text', ''))
        length_score = min(text_length / 200.0, 1.0) if text_length <= 200 else 200.0 / text_length
        content_scores.append(length_score)
        
        return sum(content_scores) / len(content_scores)

    def calculate_interaction_score(self, tweet: Dict[str, Any]) -> float:
        """
        Evaluate interaction quality based on reply behavior and mentions.
        
        Args:
            tweet (Dict[str, Any]): Tweet data containing interaction information
            
        Returns:
            float: Interaction score between 0 and 1
            
        Evaluates:
        - Conversation participation
        - Appropriate mention usage (optimal: 1-2 mentions)
        - Self-thread creation
        """
        interaction_scores = []
        
        # Score for being part of a conversation
        is_conversation = bool(tweet.get('ConversationID'))
        interaction_scores.append(1.0 if is_conversation else 0.0)
        
        # Score for appropriate mention usage
        mentions = tweet.get('Mentions', [])
        mention_count = len(mentions) if mentions else 0
        mention_score = min(mention_count / 2.0, 1.0) if mention_count <= 2 else 2.0 / mention_count
        interaction_scores.append(mention_score)
        
        # Score for self-thread creation
        is_thread = tweet.get('IsSelfThread', False)
        interaction_scores.append(0.5 if is_thread else 0.0)
        
        return sum(interaction_scores) / len(interaction_scores)

    def calculate_tweet_score(self, tweet: Dict[str, Any]) -> float:
        """
        Calculate overall tweet score by combining all components.
        
        Args:
            tweet (Dict[str, Any]): Complete tweet data
            
        Returns:
            float: Final weighted score between 0 and 1
            
        Combines:
        - Engagement score (40%)
        - Content quality score (30%)
        - Interaction score (30%)
        """
        engagement_score = self.calculate_engagement_score(tweet)
        content_score = self.calculate_content_quality_score(tweet)
        interaction_score = self.calculate_interaction_score(tweet)
        
        final_score = (
            engagement_score * self.weights['engagement'] +
            content_score * self.weights['content_quality'] +
            interaction_score * self.weights['interaction']
        )
        
        return final_score

    def score_posts(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score a list of posts and return scored results.
        
        Args:
            posts (List[Dict[str, Any]]): List of posts containing tweets to score
            
        Returns:
            List[Dict[str, Any]]: Scored posts with the following structure:
                {
                    'uid': str,
                    'user_id': str,
                    'subnet_id': str,
                    'created_at': int,
                    'scores': List[Dict] containing per-tweet scores,
                    'average_score': float
                }
        """
        scored_posts = []
        
        for post in posts:
            post_scores = []
            for tweet in post.get('tweets', []):
                tweet_data = tweet.get('Tweet', {})
                score = self.calculate_tweet_score(tweet_data)
                post_scores.append({
                    'tweet_id': tweet_data.get('ID'),
                    'score': score,
                    'timestamp': tweet_data.get('Timestamp')
                })
            
            scored_posts.append({
                'uid': post.get('uid'),
                'user_id': post.get('user_id'),
                'subnet_id': post.get('subnet_id'),
                'created_at': post.get('created_at'),
                'scores': post_scores,
                'average_score': sum(s['score'] for s in post_scores) / len(post_scores) if post_scores else 0
            })
            
        return scored_posts

# Example usage
if __name__ == "__main__":
    from protocol.data_processing.post_loader import LoadPosts
    
    # Load posts
    posts_loader = LoadPosts()
    posts = posts_loader.load_posts()
    
    # Score posts
    scorer = PostScorer()
    scored_posts = scorer.score_posts(posts)
    
    # Print results
    for post in scored_posts[:5]:  # First 5 posts
        print(f"UID: {post['uid']}")
        print(f"Average Score: {post['average_score']:.3f}")
        print("Individual Tweet Scores:")
        for score in post['scores']:
            print(f"  Tweet {score['tweet_id']}: {score['score']:.3f}")
        print()
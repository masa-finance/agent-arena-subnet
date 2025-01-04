from typing import Dict, List, Any
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta, UTC

class AgentScorer:
    def __init__(self):
        self.engagement_weights = {
            'likes': 2.0,
            'retweets': 1.5,
            'replies': 1.0,
            'views': 0.1
        }
        self.length_weight = 0.5
        self.scaler = MinMaxScaler(feature_range=(0, 1))

    def _calculate_post_score(self, post: Dict[str, Any]) -> float:
        base_score = 0
        
        # Extract tweet data from nested structure
        tweet_data = post.get('Tweet', {})
        
        # Calculate text length score
        text = tweet_data.get('Text', '')
        text_length = len(str(text))
        base_score += text_length * self.length_weight
        
        # Map the field names to our scoring metrics
        metric_mapping = {
            'likes': 'Likes',
            'retweets': 'Retweets', 
            'replies': 'Replies',
            'views': 'Views'
        }
        
        # Calculate engagement score
        for metric, weight in self.engagement_weights.items():
            field_name = metric_mapping[metric]
            value = tweet_data.get(field_name, 0)
            base_score += value * weight
                
        return np.log1p(base_score)

    def calculate_agent_scores(self, posts: List[Dict[str, Any]], 
                             time_window: int = 24) -> Dict[int, float]:
        current_time = datetime.now(UTC)
        cutoff_time = current_time - timedelta(hours=time_window)
        
        agent_posts: Dict[int, List[float]] = {}
        skipped_posts = 0
        processed_posts = 0
        
        for post_group in posts:
            try:
                uid = int(post_group.get('uid', 0))
                if not uid:
                    skipped_posts += 1
                    continue
                    
                tweets = post_group.get('tweets', [])
                for tweet in tweets:
                    try:
                        tweet_data = tweet.get('Tweet', {})
                        if not tweet_data:
                            skipped_posts += 1
                            continue
                            
                        timestamp = tweet_data.get('Timestamp')
                        if timestamp:
                            timestamp = datetime.fromtimestamp(timestamp, UTC)
                        else:
                            timestamp = current_time
                        
                        if timestamp >= cutoff_time:
                            if uid not in agent_posts:
                                agent_posts[uid] = []
                            score = self._calculate_post_score(tweet)
                            agent_posts[uid].append(score)
                            processed_posts += 1
                            
                    except Exception as e:
                        skipped_posts += 1
                        continue
                    
            except Exception as e:
                skipped_posts += 1
                continue

        print(f"Processed {processed_posts} posts, skipped {skipped_posts}")
        print(f"Found posts for {len(agent_posts)} unique agents")

        final_scores = {}
        for uid, scores in agent_posts.items():
            if scores:
                mean_score = np.mean(scores)
                post_count = len(scores)
                final_score = mean_score * np.log1p(post_count)
                final_scores[uid] = final_score

        if final_scores:
            scores_array = np.array(list(final_scores.values())).reshape(-1, 1)
            normalized_scores = self.scaler.fit_transform(scores_array).flatten()
            final_scores = {uid: score for uid, score in 
                          zip(final_scores.keys(), normalized_scores)}

        return final_scores 
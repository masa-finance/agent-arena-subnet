from typing import Dict, List, Any
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime, timedelta

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
        text_length = len(str(post.get('text', '')))
        base_score += text_length * self.length_weight
        
        for metric, weight in self.engagement_weights.items():
            if metric in post:
                base_score += post[metric] * weight
                
        return np.log1p(base_score)

    def calculate_agent_scores(self, posts: List[Dict[str, Any]], 
                             time_window: int = 24) -> Dict[int, float]:
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=time_window)
        
        agent_posts: Dict[int, List[float]] = {}
        
        for post in posts:
            uid = int(post['uid'])
            timestamp = datetime.fromtimestamp(post['timestamp'])
            
            if timestamp >= cutoff_time:
                if uid not in agent_posts:
                    agent_posts[uid] = []
                score = self._calculate_post_score(post)
                agent_posts[uid].append(score)

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
from typing import List, Tuple, Dict, Any
import math
from .post_scorer import PostScorer

class MinerWeights:
    """
    MinerWeights converts scored posts into miner weights by aggregating 
    post scores and applying volume bonuses.
    """

    def __init__(self, post_scorer: PostScorer = None):
        self.post_scorer = post_scorer or PostScorer()

    def calculate_weights(self, scored_posts: List[Dict[str, Any]]) -> Tuple[List[int], List[float]]:
        """Calculate miner weights based on post scores and volume metrics.
        
        Args:
            scored_posts: List of scored posts from PostScorer
            
        Returns:
            Tuple[List[int], List[float]]: UIDs and their corresponding weights
        """
        uids = list(set([int(post["uid"]) for post in scored_posts]))
        scores_by_uid = {}
        
        # Initialize score accumulators
        for uid in uids:
            scores_by_uid[uid] = {
                'score_sum': 0.0,
                'post_count': 0
            }
        
        # Calculate scores
        for post in scored_posts:
            uid = int(post["uid"])
            for score_data in post['scores']:
                scores_by_uid[uid]['score_sum'] += score_data['score']
                scores_by_uid[uid]['post_count'] += 1

        # Calculate final weights with volume bonus
        final_weights = {}
        for uid in uids:
            data = scores_by_uid[uid]
            if data['post_count'] > 0:
                base_score = data['score_sum'] / data['post_count']
                volume_bonus = math.log1p(data['post_count']) / 10
                final_weights[uid] = min(1.0, base_score * (1 + volume_bonus))
            else:
                final_weights[uid] = 0.0

        # Return UIDs and weights in matching order
        weights = [final_weights[uid] for uid in uids]
        return uids, weights 
from typing import List, Tuple, Dict, Any
from .post_scorer import PostScorer
from .agent_scorer import AgentScorer

class MinerWeights:
    def __init__(self, post_scorer: PostScorer = None, agent_scorer: AgentScorer = None):
        self.post_scorer = post_scorer or PostScorer()
        self.agent_scorer = agent_scorer or AgentScorer()

    def calculate_weights(self, scored_posts: List[Dict[str, Any]]) -> Tuple[List[int], List[float]]:
        # Use new agent scorer
        agent_scores = self.agent_scorer.calculate_agent_scores(scored_posts)
        
        # Convert to ordered lists
        uids = sorted(agent_scores.keys())
        weights = [agent_scores[uid] for uid in uids]
        
        return uids, weights 
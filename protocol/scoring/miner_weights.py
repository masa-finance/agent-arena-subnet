from typing import List, Tuple, Dict, Any
from .agent_scorer import AgentScorer

class MinerWeights:
    def __init__(self, agent_scorer: AgentScorer = None):
        self.agent_scorer = agent_scorer or AgentScorer()

    def calculate_weights(self, scored_posts: List[Dict[str, Any]]) -> Tuple[List[int], List[float]]:
        agent_scores = self.agent_scorer.calculate_agent_scores(scored_posts)
        uids = sorted(agent_scores.keys())
        weights = [agent_scores[uid] for uid in uids]
        return uids, weights 
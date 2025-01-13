from typing import List, Tuple, Dict, Any
from .agent_scorer import AgentScorer
from interfaces.types import Tweet


class MinerWeights:
    def __init__(self, validator: Any):
        self.agent_scorer = AgentScorer(validator=validator)

    def calculate_weights(
        self, scored_posts: List[Tweet]
    ) -> Tuple[List[int], List[float]]:
        agent_scores = self.agent_scorer.calculate_agent_scores(scored_posts)
        uids = sorted(agent_scores.keys())
        weights = [agent_scores[uid] for uid in uids]
        return uids, weights

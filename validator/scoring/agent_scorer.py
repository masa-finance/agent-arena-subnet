from datetime import datetime, UTC, timedelta
from collections import defaultdict
import numpy as np
import torch
from typing import Dict, List, Optional
from time import time

from fiber.logging_utils import get_logger
from validator.scoring.scorers.semantic_scorer import SemanticScorer
from validator.scoring.scorers.engagement_scorer import EngagementScorer
from validator.config.scoring_config import ScoringWeights
from validator.config.aggregate_weights import AggregateWeights
from validator.config.progress_config import ProgressStages, ProgressBarConfig
from validator.get_agent_posts import GetAgentPosts
from interfaces.types import Tweet

# Constants
DEFAULT_LOOKBACK_HOURS = 2
SEMANTIC_ANALYSIS_DESC = "Semantic Analysis"

logger = get_logger(__name__)

class AgentScorer:
    """Scores agents based on their post content using semantic analysis."""
    
    def __init__(
        self,
        netuid: int,
        weights: Optional[ScoringWeights] = None,
        aggregate_weights: Optional[AggregateWeights] = None,
        lookback_hours: int = DEFAULT_LOOKBACK_HOURS
    ):
        """Initialize the agent scorer.
        
        Args:
            netuid: The subnet ID to analyze
            weights: Optional scoring weights configuration
            aggregate_weights: Optional weights for combining different scoring components
            lookback_hours: Hours to look back for posts (default 24)
        """
        self.netuid = netuid
        self.weights = weights or ScoringWeights()
        self.aggregate_weights = aggregate_weights or AggregateWeights()
        self.lookback_hours = lookback_hours
        
        # Initialize scorers
        self.semantic_scorer = SemanticScorer(weights=self.weights)
        self.engagement_scorer = EngagementScorer(weights=self.weights)
        
    async def get_agent_posts(self) -> Dict[str, List[Tweet]]:
        """Fetch and organize posts by agent for the specified time period."""
        start_date = datetime.now(UTC) - timedelta(hours=self.lookback_hours)
        
        # Initialize posts getter
        posts_getter = GetAgentPosts(
            netuid=self.netuid,
            start_date=start_date,
            end_date=datetime.now(UTC)
        )
        
        # Fetch all posts
        all_posts = await posts_getter.get()
        if not all_posts:
            logger.warning(f"No posts found in the last {self.lookback_hours} hours")
            return {}
            
        # Group posts by agent
        agent_posts = defaultdict(list)
        for post in all_posts:
            username = post.get('Username')
            if username:
                agent_posts[username].append(post)
                
        # Sort posts by timestamp for each agent
        for username, posts in agent_posts.items():
            posts.sort(key=lambda x: x.get('Timestamp', ''))
            
        return agent_posts
        
    def calculate_agent_scores(self, agent_posts: Dict[str, List[Tweet]]) -> Dict[str, float]:
        """Calculate combined scores for each agent's posts."""
        if not agent_posts:
            return {}
            
        # Create progress bar with semantic status
        total_posts = sum(len(posts) for posts in agent_posts.values())
        progress = ProgressBarConfig(
            desc="Analyzing Posts",
            total=total_posts,
            initial_status=ProgressStages.get_semantic_status(0, total_posts)
        ).create_progress_bar()
        
        agent_scores = {}
        processed = 0
        start_time = time()
        
        # Initialize engagement scorer with all posts
        all_posts = [post for posts in agent_posts.values() for post in posts]
        self.engagement_scorer.initialize_scorer(all_posts)
        
        # Track max scores for normalization
        max_semantic = 0.0
        max_engagement = 0.0
        raw_scores = {}
        
        # First pass: calculate raw scores and find maximums
        for username, posts in agent_posts.items():
            semantic_scores = []
            engagement_scores = []
            
            for post in posts:
                # Calculate semantic score
                text = post.get('Text', '')
                if text:
                    semantic_score = self.semantic_scorer.calculate_score(text)
                    semantic_scores.append(semantic_score)
                    max_semantic = max(max_semantic, semantic_score)
                
                # Calculate engagement score
                engagement_score = self.engagement_scorer.calculate_score(post)
                engagement_scores.append(engagement_score)
                max_engagement = max(max_engagement, engagement_score)
                
                processed += 1
                rate = processed / (time() - start_time)
                progress.set_postfix(
                    **ProgressStages.get_semantic_status(processed, total_posts, rate)
                )
                progress.update(1)
            
            if semantic_scores or engagement_scores:
                semantic_avg = np.mean(semantic_scores) if semantic_scores else 0.0
                engagement_avg = np.mean(engagement_scores) if engagement_scores else 0.0
                raw_scores[username] = (semantic_avg, engagement_avg)
        
        # Second pass: normalize and combine scores
        max_semantic = max_semantic if max_semantic > 0 else 1.0
        max_engagement = max_engagement if max_engagement > 0 else 1.0
        
        for username, (semantic_avg, engagement_avg) in raw_scores.items():
            # Normalize each component
            normalized_semantic = semantic_avg / max_semantic
            normalized_engagement = engagement_avg / max_engagement
            
            # Combine normalized scores using weights
            combined_score = (
                normalized_semantic * self.aggregate_weights.semantic_weight +
                normalized_engagement * self.aggregate_weights.engagement_weight
            )
            
            agent_scores[username] = combined_score
        
        progress.close()
        return agent_scores
        
    def analyze_content_stats(self, agent_posts: Dict[str, List[Tweet]]) -> Dict[str, dict]:
        """Analyze content statistics for each agent."""
        stats = {}
        for username, posts in agent_posts.items():
            texts = [post.get('Text', '') for post in posts]
            if not texts:
                continue
                
            # Calculate basic statistics
            lengths = [len(text.split()) for text in texts]
            
            # Calculate similarities between consecutive posts more efficiently
            similarities = []
            if len(texts) > 1:
                # Get all embeddings at once for the agent's posts
                embeddings = self.semantic_scorer.model.encode(texts, convert_to_tensor=True)
                # Calculate similarities between consecutive embeddings
                for i in range(1, len(embeddings)):
                    similarity = float(torch.nn.functional.cosine_similarity(
                        embeddings[i].unsqueeze(0), 
                        embeddings[i-1].unsqueeze(0)
                    ))
                    similarities.append(similarity)
            
            stats[username] = {
                'post_count': len(texts),
                'avg_length': np.mean(lengths),
                'max_length': max(lengths),
                'min_length': min(lengths),
                'avg_similarity': np.mean(similarities) if similarities else 0,
                'max_similarity': max(similarities) if similarities else 0,
                'min_similarity': min(similarities) if similarities else 0
            }
            
        return stats
        
    async def score_agents(self) -> tuple[Dict[str, float], Dict[str, dict]]:
        """Score agents and analyze their content.
        
        Returns:
            Tuple of (agent_scores, content_stats)
        """
        # Fetch posts
        agent_posts = await self.get_agent_posts()
        
        if not agent_posts:
            logger.warning("No agent posts found to analyze")
            return {}, {}
            
        # Calculate scores and stats
        agent_scores = self.calculate_agent_scores(agent_posts)
        content_stats = self.analyze_content_stats(agent_posts)
        
        return agent_scores, content_stats

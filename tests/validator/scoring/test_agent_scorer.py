import pytest
import asyncio
from validator.scoring.agent_scorer import AgentScorer
from validator.config.progress_config import ProgressStages
from validator.config.aggregate_weights import AggregateWeights
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_agent_scoring():
    """Test scoring all agents' posts from the last 24 hours."""
    try:
        # Initialize scorer for subnet 59 with default weights
        scorer = AgentScorer(
            netuid=59,
            aggregate_weights=AggregateWeights()  # Using default 0.6 semantic, 0.4 engagement
        )
        
        # Get scores and stats
        agent_scores, content_stats = await scorer.score_agents()
        
        # Basic validation
        assert isinstance(agent_scores, dict), "Agent scores should be a dictionary"
        assert isinstance(content_stats, dict), "Content stats should be a dictionary"
        
        if not agent_scores:
            logger.warning("No agent scores found")
            return
            
        print(f"\n=== Top 20 Agents Analysis ===")
        print(f"Total Agents Analyzed: {len(agent_scores)}")
        print(f"Weights - Semantic: {scorer.aggregate_weights.semantic_weight:.1f}, "
              f"Engagement: {scorer.aggregate_weights.engagement_weight:.1f}")
        
        # Sort agents by score and get top 20
        top_agents = sorted(
            [(username, score, content_stats.get(username, {})) 
             for username, score in agent_scores.items()],
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        print("\nTop 20 Agents by Combined Score:")
        print("-" * 80)
        for rank, (username, score, stats) in enumerate(top_agents, 1):
            print(f"\n{rank}. @{username}")
            print(f"Combined Score: {score:.3f}")
            print(f"Activity Stats:")
            print(f"- Posts: {stats.get('post_count', 0)}")
            print(f"- Avg Post Length: {stats.get('avg_length', 0):.1f} words")
            
            if stats.get('avg_similarity', 0) > 0:
                print(f"Content Diversity:")
                print(f"- Similarity Score: {stats.get('avg_similarity', 0):.3f}")
                print(f"- Range: {stats.get('min_similarity', 0):.3f} - {stats.get('max_similarity', 0):.3f}")
            
            print(f"Post Length Range: {stats.get('min_length', 0)} - {stats.get('max_length', 0)} words")
        
        # Summary statistics for top 20
        top_20_scores = [score for _, score, _ in top_agents]
        print("\nTop 20 Summary Statistics:")
        print(f"Average Score: {sum(top_20_scores) / len(top_20_scores):.3f}")
        print(f"Score Range: {min(top_20_scores):.3f} - {max(top_20_scores):.3f}")
        
        # Print score distribution
        scores = list(agent_scores.values())
        if scores:
            print("\nScore Distribution:")
            print(f"- Average Score: {sum(scores) / len(scores):.3f}")
            print(f"- Highest Score: {max(scores):.3f}")
            print(f"- Lowest Score: {min(scores):.3f}")
            
            # Score brackets
            brackets = [(0.8, 1.0), (0.6, 0.8), (0.4, 0.6), (0.2, 0.4), (0, 0.2)]
            print("\nScore Brackets:")
            for low, high in brackets:
                count = len([s for s in scores if low <= s < high])
                percentage = (count / len(scores)) * 100
                print(f"{low:.1f} - {high:.1f}: {count} agents ({percentage:.1f}%)")
            
    except Exception as e:
        logger.error(f"Error in agent analysis: {str(e)}")
        raise

@pytest.mark.asyncio
async def test_different_weights():
    """Test scoring with different weight configurations."""
    try:
        # Test with different weight configurations
        weight_configs = [
            AggregateWeights(semantic_weight=0.8, engagement_weight=0.2),
            AggregateWeights(semantic_weight=0.4, engagement_weight=0.6)
        ]
        
        for weights in weight_configs:
            print(f"\n=== Testing weights: Semantic={weights.semantic_weight:.1f}, "
                  f"Engagement={weights.engagement_weight:.1f} ===")
            
            scorer = AgentScorer(netuid=59, aggregate_weights=weights)
            agent_scores, _ = await scorer.score_agents()
            
            if agent_scores:
                scores = list(agent_scores.values())
                print(f"Average Score: {sum(scores) / len(scores):.3f}")
                print(f"Score Range: {min(scores):.3f} to {max(scores):.3f}")
            else:
                print("No scores generated")
                
    except Exception as e:
        logger.error(f"Error in weights testing: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agent_scoring())
    asyncio.run(test_different_weights())

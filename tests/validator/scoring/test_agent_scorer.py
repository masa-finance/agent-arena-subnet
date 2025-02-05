import pytest
import asyncio
from validator.scoring.agent_scorer import AgentScorer
from validator.config.progress_config import ProgressStages
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

@pytest.mark.asyncio
async def test_agent_scoring():
    """Test scoring all agents' posts from the last 24 hours."""
    try:
        # Initialize scorer for subnet 59
        scorer = AgentScorer(netuid=59)
        
        # Get scores and stats
        agent_scores, content_stats = await scorer.score_agents()
        
        # Basic validation
        assert isinstance(agent_scores, dict), "Agent scores should be a dictionary"
        assert isinstance(content_stats, dict), "Content stats should be a dictionary"
        
        if not agent_scores:
            logger.warning("No agent scores found")
            return
            
        # Print results with progress stage information
        print(f"\n=== Content Originality Analysis ({ProgressStages.COMPLETE}) ===")
        print(f"Total Agents Analyzed: {len(agent_scores)}")
        
        print("\nAgent Analysis:")
        for username, score in sorted(agent_scores.items(), key=lambda x: x[1], reverse=True):
            stats = content_stats.get(username, {})
            print(f"\nAgent: {username}")
            print(f"Originality Score: {score:.3f}")  # More specific about what score means
            print(f"Total Posts: {stats.get('post_count', 0)}")
            print(f"Average Post Length: {stats.get('avg_length', 0):.1f} words")
            print(f"Content Similarity to Previous Posts: {stats.get('avg_similarity', 0):.3f}")
            if stats.get('max_similarity', 0) > 0:
                print(f"Highest Content Similarity: {stats.get('max_similarity', 0):.3f}")
            if stats.get('min_similarity', 0) > 0:
                print(f"Lowest Content Similarity: {stats.get('min_similarity', 0):.3f}")
            
    except Exception as e:
        logger.error(f"Error in content originality analysis: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agent_scoring())

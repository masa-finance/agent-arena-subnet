import pytest
import os
from validator.registration import ValidatorRegistration
from validator.scoring.scorers.follower_scorer import FollowerScorer
from interfaces.types import RegisteredAgentResponse

@pytest.mark.asyncio
async def test_follower_scores_from_live_api():
    """Test follower scoring using live API data"""
    
    # Mock validator for registration (minimal implementation)
    class MockValidator:
        def __init__(self):
            self.netuid = 59  # Subnet59
            self.registered_agents = {}
    
    # Initialize registration client
    validator = MockValidator()
    registration = ValidatorRegistration(validator)
    
    # Fetch real agents from API
    await registration.fetch_registered_agents()
    
    # Convert registered agents to format expected by scorer
    posts = []
    for agent in validator.registered_agents.values():
        posts.append({
            "FollowersCount": agent.FollowersCount,
            "Username": agent.Username
        })
    
    # Initialize and run scorer
    scorer = FollowerScorer(weights={'min_followers': 100})
    scorer.initialize_scorer(posts)
    
    # Calculate and store scores
    agent_scores = []
    for agent in validator.registered_agents.values():
        score = scorer.calculate_score({"FollowersCount": agent.FollowersCount})
        agent_scores.append({
            "username": agent.Username,
            "followers": agent.FollowersCount,
            "score": score
        })
    
    # Sort by score descending
    agent_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Print results
    print("\nAgent Follower Scores:")
    print("=" * 60)
    print(f"{'Username':<20} {'Followers':<12} {'Score':<10}")
    print("-" * 60)
    for agent in agent_scores:
        print(f"{agent['username']:<20} {agent['followers']:<12} {agent['score']:.4f}")
    
    # Basic assertions
    assert len(agent_scores) > 0, "No agents were scored"
    assert all(0 <= score['score'] <= 1 for score in agent_scores), "Scores should be between 0 and 1"
    assert agent_scores[0]['score'] >= agent_scores[-1]['score'], "Scores should be sorted descending" 
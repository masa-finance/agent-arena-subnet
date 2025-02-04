import pytest
import os
import numpy as np
from unittest.mock import Mock
from validator.registration import ValidatorRegistration
from validator.scoring.scorers.verification_scorer import VerificationScorer
from validator.config.scoring_config import ScoringWeights
from interfaces.types import Tweet
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

@pytest.fixture
def mock_weights():
    weights = Mock()
    weights.verification = Mock()
    weights.verification.minimum_score = 0.5
    weights.verification.unverified_cap = 0.2
    return weights

@pytest.fixture
def scorer(mock_weights):
    return VerificationScorer(weights=mock_weights)

@pytest.fixture
def sample_tweet() -> Tweet:
    return {
        "UserID": "123456",
        "IsVerified": True,
        "Text": "Test tweet",
        "Timestamp": 1234567890,
        "Likes": 10,
        "Retweets": 5,
        "Replies": 3,
        "Views": 100
    }

def test_initialization(scorer):
    """Test scorer initialization"""
    assert isinstance(scorer, VerificationScorer)
    assert hasattr(scorer, 'weights')
    assert scorer.weights.verification.minimum_score == 0.5
    assert scorer.weights.verification.unverified_cap == 0.2

def test_calculate_score(scorer, sample_tweet):
    """Test basic score calculation"""
    score = scorer.calculate_score(sample_tweet)
    assert isinstance(score, float)
    assert score == float(sample_tweet["IsVerified"])

@pytest.mark.asyncio
async def test_verification_scores_from_live_api():
    """Test verification scoring using live API data"""
    
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
    
    # Initialize scorer with real weights
    weights = ScoringWeights()
    scorer = VerificationScorer(weights=weights)
    
    # Separate verified and unverified agents
    verified_scores = {}
    unverified_scores = {}
    
    # Process each agent
    for uid, agent in validator.registered_agents.items():
        post = {
            "UserID": agent.UserID,
            "IsVerified": agent.IsVerified,
            "Username": agent.Username
        }
        score = scorer.calculate_score(post)
        
        if agent.IsVerified:
            verified_scores[uid] = score
        else:
            unverified_scores[uid] = score
    
    # Scale scores
    scaled_verified, scaled_unverified = scorer.scale_scores(verified_scores, unverified_scores)
    
    # Combine results for display
    agent_scores = []
    for uid, score in scaled_verified.items():
        agent = validator.registered_agents[uid]
        agent_scores.append({
            "username": agent.Username,
            "verified": True,
            "score": score
        })
    
    for uid, score in scaled_unverified.items():
        agent = validator.registered_agents[uid]
        agent_scores.append({
            "username": agent.Username,
            "verified": False,
            "score": score
        })
    
    # Sort by score descending
    agent_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Print results
    print("\nAgent Verification Scores:")
    print("=" * 60)
    print(f"{'Username':<20} {'Verified':<10} {'Score':<10}")
    print("-" * 60)
    for agent in agent_scores:
        print(f"{agent['username']:<20} {str(agent['verified']):<10} {agent['score']:.4f}")
    
    # Assertions
    assert len(agent_scores) > 0, "No agents were scored"
    assert all(0 <= score['score'] <= 1 for score in agent_scores), "Scores should be between 0 and 1"
    
    # Verify that verified accounts are 1.0 and unverified are 0.0
    if scaled_verified and scaled_unverified:
        assert all(score == 1.0 for score in scaled_verified.values()), "Verified scores should be 1.0"
        assert all(score == 0.0 for score in scaled_unverified.values()), "Unverified scores should be 0.0"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
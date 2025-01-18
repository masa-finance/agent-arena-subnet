import pytest
import asyncio
from validator.scorers.profile_scorer import ProfileScorer
from validator.registration import ValidatorRegistration

@pytest.mark.asyncio
async def test_profile_scores_from_api():
    """Test profile scoring with real data from registration API"""
    scorer = ProfileScorer()
    
    class MockValidator:
        netuid = 59
        registered_agents = {}
    
    registration = ValidatorRegistration(MockValidator())
    
    try:
        await registration.fetch_registered_agents()
        
        # Count profiles with followers
        profiles_with_followers = [
            agent for agent in registration.validator.registered_agents.values()
            if agent.FollowersCount > 0
        ]
        
        total_agents = len(registration.validator.registered_agents)
        
        print(f"\nProfile Statistics for Subnet 59:")
        print("-" * 50)
        print(f"Total Profiles: {total_agents}")
        print(f"Profiles with Followers: {len(profiles_with_followers)}")
        print("-" * 50)
        
        if profiles_with_followers:
            print("\nProfiles with Followers:")
            print("-" * 90)
            print(f"{'Username':<20} {'Followers':<12} {'Verified':<10} {'Score':<8} {'Joined':<20}")
            print("-" * 90)
            
            for agent in sorted(profiles_with_followers, key=lambda x: x.FollowersCount, reverse=True):
                score = scorer.calculate_score(
                    followers_count=agent.FollowersCount,
                    is_verified=agent.IsVerified
                )
                
                print(f"{agent.Username[:20]:<20} {agent.FollowersCount:<12} {str(agent.IsVerified):<10} {score:.4f} {agent.Joined[:19]}")
        else:
            print("\nNo profiles found with followers > 0")
            
        # Print sample agent data for debugging
        print("\nSample Agent Data:")
        if registration.validator.registered_agents:
            sample_agent = next(iter(registration.validator.registered_agents.values()))
            print(f"SubnetID: {sample_agent.SubnetID}")
            print(f"Sample Agent Fields: {vars(sample_agent)}")
        else:
            print("No agents found in database")
            
    except Exception as e:
        print(f"Error fetching agents: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_profile_scores_from_api())
import pytest
import os
from validator.registration import ValidatorRegistration
from loguru import logger
import httpx


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for all tests"""
    logger.remove()  # Remove default handler
    logger.add(
        sink=lambda msg: print(msg),
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )


def test_registration():
    pass


class MockValidator:
    """Simple validator mock that provides only the required attributes"""
    def __init__(self):
        self.netuid = 59
        self.registered_agents = {}


@pytest.mark.asyncio
async def test_fetch_registered_agents_live():
    """Integration test that fetches real agents from the Protocol API"""
    try:
        # Create minimal validator mock
        validator = MockValidator()
        
        # Initialize registration with real API connection
        registration = ValidatorRegistration(validator)
        
        # Configure client with timeout
        registration.httpx_client = httpx.AsyncClient(
            base_url=registration.api_url,
            headers=registration.httpx_client.headers,
            timeout=30.0
        )
        
        # Log API URL being used
        logger.info(f"Connecting to API at: {registration.api_url}")
        
        try:
            # Fetch actual agents
            await registration.fetch_registered_agents()
            
            # Initialize counters
            verified_count = 0
            unverified_count = 0
            
            # Log results and count verification status
            logger.info(f"Successfully fetched {len(validator.registered_agents)} agents")
            
            # Process each agent
            for hotkey, agent in validator.registered_agents.items():
                # Count verification status
                if agent.IsVerified:
                    verified_count += 1
                else:
                    unverified_count += 1
                
                # Log agent details
                logger.info(f"Found agent: {agent.Username} (Hotkey: {hotkey})")
                logger.info(f"  Followers: {agent.FollowersCount}")
                logger.info(f"  Verified: {agent.IsVerified}")
                logger.info(f"  Active: {agent.IsActive}")
            
            # Log verification summary
            total_agents = len(validator.registered_agents)
            logger.info("\n=== Verification Summary ===")
            logger.info(f"Total Agents: {total_agents}")
            logger.info(f"Verified Agents: {verified_count} ({(verified_count/total_agents*100):.1f}%)")
            logger.info(f"Unverified Agents: {unverified_count} ({(unverified_count/total_agents*100):.1f}%)")
            logger.info("========================")
            
            return validator.registered_agents
            
        except httpx.TimeoutException as e:
            logger.error(f"Timeout while connecting to API: {str(e)}")
            logger.error(f"Consider increasing the timeout or checking API availability")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            logger.error(f"Status code: {e.response.status_code if hasattr(e, 'response') else 'N/A'}")
            logger.error(f"Response text: {e.response.text if hasattr(e, 'response') else 'N/A'}")
            raise
        finally:
            await registration.httpx_client.aclose()
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio
    
    # Configure logging
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg),
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )
    
    # Run the test
    agents = asyncio.run(test_fetch_registered_agents_live())

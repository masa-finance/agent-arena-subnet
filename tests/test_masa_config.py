from masa_ai.masa import Masa as MasaSDK
from protocol.x.masa.masa import Masa
from loguru import logger
import pytest

@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for all tests"""
    logger.remove()  # Remove default handler
    logger.add(
        sink=lambda msg: print(msg),
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )

def test_config_override():
    # First, let's see default SDK settings
    default_masa = MasaSDK()
    logger.info("Default SDK Settings:")
    logger.debug("Twitter Settings:")
    for key in ['BASE_URL', 'TWEETS_PER_REQUEST', 'MAX_RETRIES']:
        value = default_masa.global_settings.get(f'twitter.{key}')
        logger.debug(f"  {key}: {value}")
    
    # Now initialize with our custom settings
    logger.info("\nInitializing with custom settings...")
    custom_url = "http://test.com/api/v1/"
    masa = Masa(base_url=custom_url)
    
    logger.info("Custom Settings Applied:")
    logger.debug("Twitter Settings:")
    for key in ['BASE_URL', 'TWEETS_PER_REQUEST', 'MAX_RETRIES']:
        value = masa.masa_client.global_settings.get(f'twitter.{key}')
        logger.debug(f"  {key}: {value}")
    
    # Validate specific settings we care about
    assert masa.masa_client.global_settings.get('twitter.BASE_URL') == custom_url
    assert masa.masa_client.global_settings.get('twitter.TWEETS_PER_REQUEST') == 150
    
    logger.success("Configuration override successful!")

if __name__ == "__main__":
    setup_logging()
    test_config_override()
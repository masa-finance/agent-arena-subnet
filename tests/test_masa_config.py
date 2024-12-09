from masa_ai import Masa as MasaSDK
from protocol.x.masa import Masa
from loguru import logger

def test_config_override():
    # First, let's see default SDK settings
    default_masa = MasaSDK()
    logger.info("Default SDK Settings:")
    logger.info(f"Twitter Base URL: {default_masa.global_settings.get('twitter.BASE_URL')}")
    logger.info(f"Tweets per request: {default_masa.global_settings.get('twitter.TWEETS_PER_REQUEST')}")
    
    # Now initialize with our custom settings
    masa = Masa()
    logger.info("\nOur Custom Settings:")
    logger.info(f"Twitter Base URL: {masa.masa_client.global_settings.get('twitter.BASE_URL')}")
    logger.info(f"Tweets per request: {masa.masa_client.global_settings.get('twitter.TWEETS_PER_REQUEST')}")
    
    # Validate specific settings we care about
    assert masa.masa_client.global_settings.get('twitter.BASE_URL') == "http://localhost:8080/api/v1/"
    assert masa.masa_client.global_settings.get('twitter.TWEETS_PER_REQUEST') == 150
    
    logger.success("Configuration override successful!")

if __name__ == "__main__":
    test_config_override()
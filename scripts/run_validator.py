import asyncio
import os
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from neurons.validator import AgentValidator
from dotenv import load_dotenv

logger = get_logger(__name__)

async def main():
    validator = None
    try:
        # Load environment variables from .env file
        load_dotenv()
        
        # Get network configuration from environment variables
        network = os.getenv("SUBTENSOR_NETWORK", "finney")
        network_address = os.getenv("SUBTENSOR_ADDRESS", "wss://entrypoint-finney.opentensor.ai:443")
        
        # Get NETUID from environment variable
        netuid = os.getenv("NETUID", "1")  # Default to 1 if not set
        os.environ["NETUID"] = netuid
        
        # Get seed phrase from environment variable
        seed_phrase = os.getenv("SEED_PHRASE")
        if not seed_phrase:
            raise ValueError("SEED_PHRASE environment variable is not set")
            
        keypair = Keypair.create_from_mnemonic(seed_phrase)
        
        # Create validator with network settings
        validator = AgentValidator()
        
        # Start the validator on port 8081
        await validator.start(keypair=keypair, port=8081)
            
    except KeyboardInterrupt:
        logger.info("Shutting down validator...")
        if validator:
            await validator.stop()
    except Exception as e:
        logger.error(f"Error running validator: {str(e)}")
        if validator:
            await validator.stop()

if __name__ == "__main__":
    asyncio.run(main())
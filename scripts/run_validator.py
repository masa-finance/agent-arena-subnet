import asyncio
import os
from fiber.logging_utils import get_logger
from neurons.validator import AgentValidator
from dotenv import load_dotenv
from fiber.chain import chain_utils

logger = get_logger(__name__)

async def main():
    validator = None
    try:
        # Load environment variables from .env file
        load_dotenv()
    
        wallet_name = os.getenv("VALIDATOR_WALLET_NAME", "validator")
        hotkey_name = os.getenv("VALIDATOR_HOTKEY_NAME", "default")
        port = int(os.getenv("VALIDATOR_PORT", 8081))

        keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)
        
        # Create validator with network settings
        validator = AgentValidator()
        
        # Start the validator on port 8081
        await validator.start(keypair=keypair, port=port)
            
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
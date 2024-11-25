import asyncio
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from neurons.validator import AgentValidator

logger = get_logger(__name__)

async def main():
    try:
        # Initialize your keypair (replace with your actual seed phrase)
        seed_phrase = "enough insect jump blossom theory tail yellow nation point vicious very magic"
        keypair = Keypair.create_from_mnemonic(seed_phrase)
        
        # Create and start validator without Twitter service
        validator = AgentValidator()
        
        # Start the validator on port 8081 (or choose your preferred port)
        await validator.start(keypair=keypair, port=8081)
        
        # Keep the validator running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down validator...")
        await validator.stop()
    except Exception as e:
        logger.error(f"Error running validator: {str(e)}")
        await validator.stop()

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import os
from fiber.logging_utils import get_logger
from neurons.validator import AgentValidator
from dotenv import load_dotenv
from fiber.chain import chain_utils

logger = get_logger(__name__)


async def main():
    # Load env
    load_dotenv()

    wallet_name = os.getenv("VALIDATOR_WALLET_NAME", "validator")
    hotkey_name = os.getenv("VALIDATOR_HOTKEY_NAME", "default")
    port = int(os.getenv("VALIDATOR_PORT", 8081))

    keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)

    # Initialize validator
    validator = AgentValidator()
    await validator.start(keypair=keypair, port=port)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await validator.stop()


if __name__ == "__main__":
    asyncio.run(main())

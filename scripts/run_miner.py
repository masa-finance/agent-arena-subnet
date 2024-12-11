# scripts/run_miner.py
import os
import asyncio
from dotenv import load_dotenv
from fiber.chain import chain_utils
from neurons.miner import AgentMiner
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


async def main():
    # Load env
    load_dotenv()

    wallet_name = os.getenv("WALLET_NAME", "miner")
    hotkey_name = os.getenv("HOTKEY_NAME", "default")
    port = int(os.getenv("MINER_PORT", 8080))

    keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)

    # Initialize miner
    miner = AgentMiner()
    await miner.start(keypair=keypair, port=port)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await miner.stop()


if __name__ == "__main__":
    asyncio.run(main())

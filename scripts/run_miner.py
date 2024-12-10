# scripts/run_miner.py
import os
import asyncio
from dotenv import load_dotenv
from fiber.chain import chain_utils
from neurons.miner import AgentMiner


async def main():
    # Load env
    load_dotenv()
    wallet_name = os.getenv("MINER_WALLET_NAME", "miner")
    hotkey_name = os.getenv("MINER_HOTKEY_NAME", "default")

    keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)

    # Initialize miner
    miner = AgentMiner()
    await miner.start(
        keypair=keypair, miner_hotkey_ss58_address=keypair.public_key, port=8080
    )

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await miner.stop()


if __name__ == "__main__":
    asyncio.run(main())

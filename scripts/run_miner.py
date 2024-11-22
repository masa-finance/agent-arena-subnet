# scripts/run_miner.py
import os
import asyncio
from dotenv import load_dotenv
from fiber.chain import chain_utils, interface
from neurons.miner import AgentMiner

async def main():
    # Load env
    load_dotenv("dev.env")
    wallet_name = os.getenv("WALLET_NAME", "default")
    hotkey_name = os.getenv("HOTKEY_NAME", "default")

    # Initialize substrate using Fiber (not Bittensor)
    substrate = interface.get_substrate(subtensor_network="finney")
    keypair = chain_utils.load_hotkey_keypair(wallet_name, hotkey_name)

    # Initialize miner
    miner = AgentMiner()
    await miner.start(
        keypair=keypair,
        validator_address="http://localhost:8081",
        port=8080
    )

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await miner.stop()

if __name__ == "__main__":
    asyncio.run(main())
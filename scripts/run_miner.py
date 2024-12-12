import asyncio
from dotenv import load_dotenv
from neurons.miner import AgentMiner


async def main():
    # Load env
    load_dotenv()

    # Initialize miner
    miner = AgentMiner()
    await miner.start()

    # Keyboard handler
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await miner.stop()


if __name__ == "__main__":
    asyncio.run(main())

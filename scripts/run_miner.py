import asyncio
from neurons.miner import AgentMiner


async def main():
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

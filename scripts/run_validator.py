import asyncio
from neurons.validator import AgentValidator


async def main():
    # Initialize validator
    validator = AgentValidator()
    await validator.start()

    # Keyboard handler
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await validator.stop()


if __name__ == "__main__":
    asyncio.run(main())

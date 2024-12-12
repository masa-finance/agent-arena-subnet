# scripts/run_miner.py
import os
import asyncio
from dotenv import load_dotenv
from fiber.chain import chain_utils
from neurons.miner import AgentMiner
from fiber.logging_utils import get_logger
import subprocess
import requests

logger = get_logger(__name__)


def get_external_ip():
    env = os.getenv("ENV", "prod").lower()
    if env == "dev":
        # post this to chain to mark as local
        return "0.0.0.1"

    try:
        response = requests.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return response.json()["ip"]
    except requests.RequestException as e:
        logger.error(f"Failed to get external IP: {e}")


def post_ip_to_chain(
    subtensor_netuid, external_ip, port, subtensor_network, wallet_name, hotkey_name
):
    try:
        result = subprocess.run(
            [
                "fiber-post-ip",
                "--netuid",
                subtensor_netuid,
                "--external_ip",
                external_ip,
                "--external_port",
                str(port),
                "--subtensor.network",
                subtensor_network,
                "--wallet.name",
                wallet_name,
                "--wallet.hotkey",
                hotkey_name,
            ],
            check=True,
        )

        if result.returncode != 0:
            logger.error("Failed to post IP to chain.")
            return

        logger.info("Successfully posted IP to chain.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to post IP to chain: {e}")


async def main():
    # Load env
    load_dotenv()

    subtensor_netuid = os.getenv("NETUID", "249")
    subtensor_network = os.getenv("SUBTENSOR_NETWORK", "test")
    wallet_name = os.getenv("WALLET_NAME", "miner")
    hotkey_name = os.getenv("HOTKEY_NAME", "default")
    port = int(os.getenv("MINER_PORT", 8080))
    external_ip = get_external_ip()

    # TODO perhaps a check here to see if the ip is already posted
    post_ip_to_chain(
        subtensor_netuid=subtensor_netuid,
        external_ip=external_ip,
        port=port,
        subtensor_network=subtensor_network,
        wallet_name=wallet_name,
        hotkey_name=hotkey_name,
    )

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

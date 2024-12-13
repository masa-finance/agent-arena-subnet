import asyncio
from fiber.chain import chain_utils, interface, weights
from fiber.chain.fetch_nodes import get_nodes_for_netuid
from fiber.logging_utils import get_logger
from dotenv import load_dotenv
import os

logger = get_logger(__name__)


async def set_weights():
    # Load environment variables
    load_dotenv()

    # Get network configuration
    network = os.getenv("SUBTENSOR_NETWORK", "test")
    netuid = int(os.getenv("NETUID", "249"))

    # Following example exactly
    substrate = interface.get_substrate(subtensor_network=network)
    nodes = get_nodes_for_netuid(substrate=substrate, netuid=netuid)

    # Load keypair
    wallet_name = os.getenv("VALIDATOR_WALLET_NAME", "testnet")
    hotkey_name = os.getenv("VALIDATOR_HOTKEY_NAME", "testnet")
    keypair = chain_utils.load_hotkey_keypair(
        wallet_name=wallet_name, hotkey_name=hotkey_name
    )

    # Get validator UID
    validator_node_id = substrate.query(
        "SubtensorModule", "Uids", [netuid, keypair.ss58_address]
    ).value

    logger.info(f"Found validator UID: {validator_node_id}")

    # Get version key
    version_key = substrate.query(
        "SubtensorModule", "WeightsVersionKey", [netuid]
    ).value

    # Wait a bit to ensure registration is fully processed
    logger.info("Waiting 30 seconds to ensure registration is fully processed...")
    await asyncio.sleep(30)

    # Check if we can set weights
    blocks_since_update = weights._blocks_since_last_update(
        substrate, netuid, validator_node_id
    )
    min_interval = weights._min_interval_to_set_weights(substrate, netuid)

    logger.info(f"Blocks since last update: {blocks_since_update}")
    logger.info(f"Minimum interval required: {min_interval}")

    if blocks_since_update is not None and blocks_since_update < min_interval:
        wait_blocks = min_interval - blocks_since_update
        logger.info(f"Need to wait {wait_blocks} more blocks before setting weights")
        # Assuming ~12 second block time
        wait_seconds = wait_blocks * 12
        logger.info(f"Waiting {wait_seconds} seconds...")
        await asyncio.sleep(wait_seconds)

    # Since we only have one node, set a single weight
    node_ids = [validator_node_id]
    node_weights = [1.0]
    logger.info(f"Setting weight {node_weights[0]} for node {node_ids[0]}")


if __name__ == "__main__":
    asyncio.run(set_weights())

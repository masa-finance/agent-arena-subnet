import asyncio
import os
from dotenv import load_dotenv
from fiber.chain import chain_utils, interface, weights
from fiber.logging_utils import get_logger

logger = get_logger(__name__)

async def set_weights():
    try:
        # Load environment variables
        load_dotenv()
        
        # Get network configuration
        network = os.getenv("SUBTENSOR_NETWORK", "test")
        netuid = int(os.getenv("NETUID", "249"))
        
        # Get substrate connection
        substrate = interface.get_substrate(subtensor_network=network)
        
        # Load keypair
        wallet_name = os.getenv("WALLET_NAME", "testnet")
        hotkey_name = os.getenv("HOTKEY_NAME", "testnet")
        keypair = chain_utils.load_hotkey_keypair(wallet_name=wallet_name, hotkey_name=hotkey_name)
        
        # Get your validator's UID (we know it's 0 from registration output)
        validator_uid = 0
        
        # Get version key
        version_key = substrate.query(
            "SubtensorModule",
            "WeightsVersionKey",
            [netuid]
        ).value
        
        # Set weights (initially just to ourselves with weight 1.0)
        success = weights.set_node_weights(
            substrate=substrate,
            keypair=keypair,
            node_ids=[validator_uid],  # Just our own UID
            node_weights=[1.0],  # Full weight to ourselves
            netuid=netuid,
            validator_node_id=validator_uid,
            version_key=version_key,
            wait_for_inclusion=True,
            wait_for_finalization=True
        )
        
        if success:
            logger.info("Successfully set initial weights!")
        else:
            logger.error("Failed to set weights")
            
    except Exception as e:
        logger.error(f"Error setting weights: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(set_weights()) 
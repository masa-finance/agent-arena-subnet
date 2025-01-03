from typing import List, Tuple, Any
import asyncio
from fiber.chain import weights, interface
from fiber.logging_utils import get_logger
from protocol.scoring.miner_weights import MinerWeights

logger = get_logger(__name__)

class ValidatorWeightSetter:
    def __init__(self, netuid: int, keypair: Any, substrate: Any, version_numerical: int):
        self.netuid = netuid
        self.keypair = keypair
        self.substrate = substrate
        self.version_numerical = version_numerical
        self.miner_weights = MinerWeights()

    def get_scores(self, scored_posts: List[Any]) -> Tuple[List[int], List[float]]:
        return self.miner_weights.calculate_weights(scored_posts)

    async def set_weights(self, scored_posts: List[Any]) -> None:
        self.substrate = interface.get_substrate(subtensor_address=self.substrate.url)
        validator_node_id = self.substrate.query(
            "SubtensorModule", "Uids", [self.netuid, self.keypair.ss58_address]
        ).value

        blocks_since_update = weights._blocks_since_last_update(
            self.substrate, self.netuid, validator_node_id
        )
        min_interval = weights._min_interval_to_set_weights(self.substrate, self.netuid)

        logger.info(f"Blocks since last update: {blocks_since_update}")
        logger.info(f"Minimum interval required: {min_interval}")

        if blocks_since_update is not None and blocks_since_update < min_interval:
            wait_blocks = min_interval - blocks_since_update
            wait_seconds = wait_blocks * 12
            logger.info(f"Waiting {wait_seconds} seconds...")
            await asyncio.sleep(wait_seconds)

        uids, scores = self.get_scores(scored_posts)

        for attempt in range(3):
            try:
                success = weights.set_node_weights(
                    substrate=self.substrate,
                    keypair=self.keypair,
                    node_ids=uids,
                    node_weights=scores,
                    netuid=self.netuid,
                    validator_node_id=validator_node_id,
                    version_key=self.version_numerical,
                    wait_for_inclusion=False,
                    wait_for_finalization=False,
                )

                if success:
                    logger.info("✅ Successfully set weights!")
                    return
                else:
                    logger.error(f"❌ Failed to set weights on attempt {attempt + 1}")
                    await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                await asyncio.sleep(10)

        logger.error("Failed to set weights after all attempts") 
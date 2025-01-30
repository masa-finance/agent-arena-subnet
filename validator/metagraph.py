from fiber.logging_utils import get_logger
from typing import Optional, Tuple, List
from fiber.networking.models import NodeWithFernet as Node
from fiber.chain import interface
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurons.validator import AgentValidator

logger = get_logger(__name__)


class MetagraphManager:
    def __init__(self, validator: "AgentValidator"):
        """
        Initialize the MetagraphManager with a validator instance.

        :param validator: The validator instance to manage the metagraph.
        """
        self.validator = validator

    def sync_substrate(self) -> None:
        """
        Sync the substrate with the latest chain state.
        """
        self.validator.substrate = interface.get_substrate(
            subtensor_address=self.validator.substrate.url
        )

    async def sync_metagraph(self) -> None:
        """
        Synchronize local metagraph state with the chain.
        """
        try:
            self.sync_substrate()
            self.validator.metagraph.sync_nodes()

            keys_to_delete = []
            for hotkey, _ in self.validator.connected_nodes.items():
                if hotkey not in self.validator.metagraph.nodes:
                    logger.info(
                        f"Hotkey: {hotkey} has been deregistered from the metagraph"
                    )
                    agent = self.validator.registered_agents.get(hotkey)
                    keys_to_delete.append(hotkey)
                    await self.validator.registrar.deregister_agent(agent)

            for hotkey in keys_to_delete:
                del self.validator.connected_nodes[hotkey]

            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def get_emissions(self, node: Optional[Node]) -> Tuple[float, List[float]]:
        self.sync_substrate()
        multiplier = 10**-9
        emissions = [
            emission * multiplier
            for emission in self.validator.substrate.query(
                "SubtensorModule", "Emission", [self.validator.netuid]
            ).value
        ]
        node_emissions = emissions[int(node.node_id)] if node else 0
        return node_emissions, emissions

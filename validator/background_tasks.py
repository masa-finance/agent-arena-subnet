import asyncio
from fiber.logging_utils import get_logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurons.validator import AgentValidator

logger = get_logger(__name__)


class BackgroundTasks:
    def __init__(self, validator: "AgentValidator"):
        """
        Initialize the BackgroundTasks with necessary components.

        :param validator: The validator instance for agent registration tasks.
        """
        self.validator = validator

    async def check_agents_registration_loop(self, cadence_seconds):
        """
        Periodically check agent registration.

        :param cadence_seconds: The interval in seconds between checks.
        """
        while True:
            try:
                await self.validator.registrar.check_agents_registration()
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error checking registered agents: {str(e)}")
                await asyncio.sleep(cadence_seconds / 2)

    async def update_agents_profiles_and_emissions_loop(self, cadence_seconds):
        """
        Periodically update agent profiles and emissions.

        :param cadence_seconds: The interval in seconds between updates.
        """
        while True:
            try:
                await self.validator.registrar.update_agents_profiles_and_emissions()
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error in updating profiles: {str(e)}")
                await asyncio.sleep(cadence_seconds / 2)

    async def set_weights_loop(self, scored_posts, cadence_seconds):
        """
        Periodically set weights based on scored posts.

        :param scored_posts: The list of scored posts.
        :param cadence_seconds: The interval in seconds between weight settings.
        """
        while True:
            try:
                if len(scored_posts) > 0:
                    await self.validator.weight_setter.set_weights(scored_posts)
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error in setting weights: {str(e)}")
                await asyncio.sleep(cadence_seconds)

    async def score_loop(self, cadence_seconds):
        """
        Periodically score agents.

        :param cadence_seconds: The interval in seconds between scoring.
        """
        while True:
            try:
                self.validator.scored_posts = await self.validator.posts_getter.get()
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error in scoring: {str(e)}")
                await asyncio.sleep(cadence_seconds / 2)

    async def sync_loop(self, cadence_seconds) -> None:
        """Background task to sync metagraph"""
        while True:
            try:
                await self.validator.registrar.fetch_registered_agents()
                await self.validator.node_manager.connect_new_nodes()
                await self.validator.metagraph_manager.sync_metagraph()
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error in sync metagraph: {str(e)}")
                await asyncio.sleep(cadence_seconds / 2)  # Wait before retrying

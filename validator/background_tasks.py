import asyncio
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


class BackgroundTasks:
    def __init__(self, registrar, posts_getter, weight_setter, scored_posts):
        """
        Initialize the BackgroundTasks with necessary components.

        :param registrar: The registrar instance for agent registration tasks.
        :param posts_getter: The posts getter instance for fetching posts.
        :param weight_setter: The weight setter instance for setting weights.
        :param scored_posts: The list of scored posts.
        """
        self.registrar = registrar
        self.posts_getter = posts_getter
        self.weight_setter = weight_setter
        self.scored_posts = scored_posts

    async def check_agents_registration_loop(self, cadence_seconds):
        """
        Periodically check agent registration.

        :param cadence_seconds: The interval in seconds between checks.
        """
        while True:
            try:
                await self.registrar.check_agents_registration()
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
                await self.registrar.update_agents_profiles_and_emissions()
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
                    await self.weight_setter.set_weights(scored_posts)
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
                self.scored_posts = await self.posts_getter.get()
                await asyncio.sleep(cadence_seconds)
            except Exception as e:
                logger.error(f"Error in scoring: {str(e)}")
                await asyncio.sleep(cadence_seconds / 2)

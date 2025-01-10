import json
import httpx
from typing import Any
from fiber.logging_utils import get_logger

from interfaces.types import (
    VerifiedTweet,
    RegisteredAgentResponse,
    RegisteredAgentRequest,
    Profile,
)

logger = get_logger(__name__)


class ValidatorRegistration:
    def __init__(
        self,
        validator: Any,
    ):
        self.validator = validator
        self.registration_endpoint = "/v1.0.0/subnet59/miners/register"
        self.active_agents_endpoint = (
            f"/v1.0.0/subnet59/miners/active/{self.validator.netuid}"
        )
        self.httpx_client = httpx.AsyncClient(
            base_url=self.validator.api_url,
            headers={"Authorization": f"Bearer {self.validator.api_key}"},
        )

    async def fetch_registered_agents(self) -> None:
        """Fetch active agents from the API and update registered_agents"""
        try:
            response = await self.httpx_client.get(self.active_agents_endpoint)
            if response.status_code == 200:
                active_agents = response.json()
                self.validator.registered_agents = {
                    agent["HotKey"]: RegisteredAgentResponse(**agent)
                    for agent in active_agents
                }
                logger.info("Successfully fetched and updated active agents.")
            else:
                logger.error(
                    f"Failed to fetch active agents, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred while fetching active agents: {str(e)}")

    async def register_agent(
        self,
        node: Any,
        verified_tweet: VerifiedTweet,
        user_id: str,
        screen_name: str,
        avatar: str,
        name: str,
    ) -> None:
        """Register an agent"""
        node_emissions, _ = self.validator.get_emissions(node)
        registration_data = RegisteredAgentRequest(
            hotkey=node.hotkey,
            uid=str(node.node_id),
            subnet_id=int(self.validator.netuid),
            version=str(node.protocol),
            isActive=True,
            verification_tweet=verified_tweet,
            emissions=node_emissions,
            profile={
                "data": Profile(
                    UserID=user_id, Username=screen_name, Avatar=avatar, Name=name
                )
            },
        )
        registration_data = json.loads(
            json.dumps(registration_data, default=lambda o: o.__dict__)
        )
        try:
            response = await self.httpx_client.post(
                self.registration_endpoint, json=registration_data
            )
            if response.status_code == 200:
                logger.info("Successfully registered agent!")
                await self.fetch_registered_agents()
            else:
                logger.error(
                    f"Failed to register agent, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent registration: {str(e)}")

    async def deregister_agent(self, agent: RegisteredAgentResponse) -> None:
        """Deregister agent with the API"""
        logger.info("Deregistering agent...")
        try:
            verification_tweet = VerifiedTweet(
                tweet_id=agent.VerificationTweetID,
                url=agent.VerificationTweetURL,
                timestamp=agent.VerificationTweetTimestamp,
                full_text=agent.VerificationTweetText,
            )
            deregistration_data = RegisteredAgentRequest(
                hotkey=agent.HotKey,
                uid=str(agent.UID),
                subnet_id=int(self.validator.netuid),
                version=str(agent.Version),
                isActive=False,
                verification_tweet=verification_tweet,
                profile={
                    "data": Profile(
                        UserID=agent.UserID,
                        Username=agent.Username,
                    )
                },
            )
            deregistration_data = json.loads(
                json.dumps(deregistration_data, default=lambda o: o.__dict__)
            )
            response = await self.httpx_client.post(
                self.registration_endpoint,
                json=deregistration_data,
            )
            if response.status_code == 200:
                logger.info("Successfully deregistered agent!")
                return response.json()
            else:
                logger.error(
                    f"Failed to deregister agent, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent deregistration: {str(e)}")

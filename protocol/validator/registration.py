import os
import json
import httpx
from datetime import datetime
from typing import Any, Optional

from fiber.logging_utils import get_logger
from fiber.networking.models import NodeWithFernet as Node

from masa_ai.tools.validator import TweetValidator

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

        # note, API key needed for POST requests (at least one validator must have)
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")
        self.api_key = os.getenv("API_KEY", None)

        # endpoints for requests to the API
        self.registration_endpoint = "/v1.0.0/subnet59/miners/register"
        self.active_agents_endpoint = (
            f"/v1.0.0/subnet59/miners/active/{self.validator.netuid}"
        )

        # http client for requests to the API
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
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
                await self.fetch_registered_agents()
            else:
                logger.error(
                    f"Failed to deregister agent, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent deregistration: {str(e)}")

    async def update_agents_profiles_and_emissions(self) -> None:
        _, emissions = self.validator.get_emissions(None)
        for hotkey, _ in self.validator.metagraph.nodes.items():
            agent = self.validator.registered_agents.get(hotkey, None)
            if agent:
                x_profile = await self.validator.fetch_x_profile(agent.Username)
                if x_profile is None:
                    # it is possible that the username has changed...
                    # attempt to refetch the username using the tweet id
                    try:
                        logger.info(
                            f"Trying to refetch username for agent: {
                                    agent.Username}"
                        )
                        verified_tweet, user_id, username, avatar, name = (
                            await self.verify_tweet(
                                agent.VerificationTweetID, agent.HotKey
                            )
                        )
                        x_profile = await self.validator.fetch_x_profile(username)
                        if x_profile is None:
                            logger.error(
                                f"Failed to fetch X profile on second attempt for {username}, continuing..."
                            )
                            continue
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch profile for {agent.Username}, continuing..."
                        )
                        continue
                try:
                    logger.info(f"X Profile To Update: {x_profile}")
                    agent_emissions = emissions[int(agent.UID)]
                    logger.info(
                        f"Emissions Updater: Agent {agent.Username} has {agent_emissions} emissions"
                    )
                    verification_tweet = VerifiedTweet(
                        tweet_id=agent.VerificationTweetID,
                        url=agent.VerificationTweetURL,
                        timestamp=agent.VerificationTweetTimestamp,
                        full_text=agent.VerificationTweetText,
                    )
                    update_data = RegisteredAgentRequest(
                        hotkey=hotkey,
                        uid=str(agent.UID),
                        subnet_id=int(self.validator.netuid),
                        version=str(4),
                        isActive=True,
                        emissions=agent_emissions,
                        verification_tweet=verification_tweet,
                        profile={
                            "data": Profile(
                                UserID=agent.UserID,
                                Username=x_profile["data"]["Username"],
                                Avatar=x_profile["data"]["Avatar"],
                                Banner=x_profile["data"]["Banner"],
                                Biography=x_profile["data"]["Biography"],
                                FollowersCount=x_profile["data"]["FollowersCount"],
                                FollowingCount=x_profile["data"]["FollowingCount"],
                                LikesCount=x_profile["data"]["LikesCount"],
                                Name=x_profile["data"]["Name"],
                            )
                        },
                    )
                    update_data = json.loads(
                        json.dumps(update_data, default=lambda o: o.__dict__)
                    )
                    response = await self.httpx_client.post(
                        self.registration_endpoint, json=update_data
                    )
                    if response.status_code == 200:
                        logger.info("Successfully updated agent!")
                    else:
                        logger.error(
                            f"Failed to update agent, status code: {
                                response.status_code}, message: {response.text}"
                        )
                except Exception as e:
                    logger.error(f"Exception occurred during agent update: {str(e)}")

    async def check_agents_registration(self) -> None:
        unregistered_nodes = []
        try:
            # Iterate over each registered node to check if it has a registered agent
            for hotkey in self.validator.connected_nodes:
                if hotkey not in self.validator.registered_agents:
                    unregistered_nodes.append(hotkey)

            # Log the unregistered nodes
            if unregistered_nodes:
                logger.info(
                    "Unregistered nodes found: %s",
                    ", ".join(node for node in unregistered_nodes),
                )
            else:
                logger.info("All nodes have registered agents.")

            for hotkey in unregistered_nodes:
                try:
                    nodes = self.validator.metagraph.nodes
                    node = nodes[hotkey]
                    if node:
                        # note, could refactor to this module but will keep vali <> miner calls in vali for now
                        tweet_id = await self.get_verification_tweet_id(node)
                        verified_tweet, user_id, screen_name, avatar, name = (
                            await self.verify_tweet(tweet_id, node.hotkey)
                        )
                        if verified_tweet and user_id:
                            await self.register_agent(
                                node,
                                verified_tweet,
                                user_id,
                                screen_name,
                                avatar,
                                name,
                            )
                            payload = {
                                "registered": str(screen_name),
                                "message": "Agent successfully registered!",
                            }
                            response = await self.registration_callback(node, payload)
                        else:
                            payload = {
                                "registered": "Agent failed to register",
                                "message": f"Failed to register with tweet {tweet_id}",
                            }
                            response = await self.registration_callback(node, payload)

                        logger.info(
                            f"Miner Response From Registration Callback: {response}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to get registration info for node {
                                hotkey}: {str(e)}"
                    )

        except Exception as e:
            logger.error("Error checking registered nodes: %s", str(e))

    async def verify_tweet(
        self, id: str, hotkey: str
    ) -> tuple[VerifiedTweet, str, str]:
        """Fetch tweet from Twitter API"""
        try:
            logger.info(f"Verifying tweet: {id}")
            result = TweetValidator().fetch_tweet(id)

            if not result:
                logger.error(
                    f"Could not fetch tweet id {
                            id} for node {hotkey}"
                )
                return False

            tweet_data_result = (
                result.get("data", {}).get("tweetResult", {}).get("result", {})
            )
            created_at = tweet_data_result.get("legacy", {}).get("created_at")
            tweet_id = tweet_data_result.get("rest_id")
            user = (
                tweet_data_result.get("core", {})
                .get("user_results", {})
                .get("result", {})
            )

            screen_name = user.get("legacy", {}).get("screen_name")
            name = user.get("legacy", {}).get("name")
            user_id = user.get("rest_id")

            full_text = tweet_data_result.get("legacy", {}).get("full_text")
            avatar = user.get("legacy", {}).get("profile_image_url_https")

            logger.info(
                f"Got tweet result: {
                        tweet_id} - {screen_name} **** {full_text} - {avatar}"
            )

            if not isinstance(screen_name, str) or not isinstance(full_text, str):
                msg = "Invalid tweet data: screen_name or full_text is not a string"
                logger.error(msg)
                raise ValueError(msg)

            # ensure hotkey is in the tweet text
            if not hotkey in full_text:
                msg = f"Hotkey {hotkey} is not in the tweet text {full_text}"
                logger.error(msg)
                raise ValueError(msg)

            verification_tweet = VerifiedTweet(
                tweet_id=tweet_id,
                url=f"https://twitter.com/{screen_name}/status/{tweet_id}",
                timestamp=datetime.strptime(
                    created_at, "%a %b %d %H:%M:%S %z %Y"
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                full_text=full_text,
            )
            return verification_tweet, user_id, screen_name, avatar, name
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return False

    async def get_verification_tweet_id(self, node: Node) -> Optional[str]:
        try:
            verification_tweet_id = await self.validator.make_non_streamed_get(
                node, "/get_verification_tweet_id"
            )
            return verification_tweet_id
        except Exception as e:
            logger.error(f"Failed to get agent tweet id: {str(e)}")
            return None

    async def registration_callback(self, node: Node, payload: Any) -> Optional[str]:
        try:
            response = await self.validator.make_non_streamed_post(
                node, "/registration_callback", payload
            )
            return response
        except Exception as e:
            logger.error(f"Failed to send registration callback: {str(e)}")
            return None

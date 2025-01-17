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
        self.deregistration_endpoint = "/v1.0.0/subnet59/miners/deregister"
        self.active_agents_endpoint = (
            f"/v1.0.0/subnet59/miners/active/{self.validator.netuid}"
        )

        # http client for requests to the API
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def fetch_registered_agents(self) -> None:
        """Fetch registered agents from the API"""
        try:
            response = await self.httpx_client.get(self.active_agents_endpoint)
            response.raise_for_status()
            agents = response.json() or []

            # Safely access the data
            self.validator.registered_agents = {
                agent["HotKey"]: RegisteredAgentResponse(**agent) for agent in agents
            }

            logger.info(
                f"Successfully fetched {len(agents)} agents for subnet {self.validator.netuid}"
            )

        except httpx.RequestError as e:
            logger.error(f"HTTP request failed: {e}")
        except Exception as e:
            logger.error(f"Exception occurred while fetching active agents: {e}")

    async def register_agent(
        self,
        node: Any,
        verified_tweet: VerifiedTweet,
        user_id: str,
        screen_name: str,
        avatar: str,
        name: str,
        is_verified: bool,
        followers_count: int,
    ) -> None:
        """Register an agent"""
        node_emissions, _ = self.validator.get_emissions(node)
        registration_data = RegisteredAgentRequest(
            ID=node.node_id,
            HotKey=node.hotkey,
            UID=str(node.node_id),
            SubnetID=int(self.validator.netuid),
            Version=str(node.protocol),
            VerificationTweet=verified_tweet,
            Emissions=node_emissions,
            Profile={
                "data": Profile(
                    UserID=user_id,
                    Username=screen_name,
                    Avatar=avatar,
                    Name=name,
                    IsVerified=is_verified,
                    FollowersCount=followers_count,
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

    async def deregister_agent(self, agent: RegisteredAgentResponse) -> bool:
        """Deregister agent with the API

        Args:
            agent: The agent to deregister

        Returns:
            bool: True if deregistration was successful, False otherwise
        """
        logger.info(f"Deregistering agent {agent.Username} (UID: {agent.UID})...")
        try:
            response = await self.httpx_client.delete(
                f"{self.deregistration_endpoint}/{self.validator.netuid}/{agent.UID}"
            )
            response.raise_for_status()
            logger.info(f"Successfully deregistered agent {agent.Username}!")
            await self.fetch_registered_agents()
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error during agent deregistration: Status {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(f"Network error during agent deregistration: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during agent deregistration: {str(e)}")
            return False

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
                        (
                            verified_tweet,
                            user_id,
                            username,
                            avatar,
                            name,
                            is_verified,
                            followers_count,
                            error,
                        ) = await self.verify_tweet(
                            agent.VerificationTweetID, agent.HotKey
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
                        TweetID=agent.VerificationTweetID,
                        URL=agent.VerificationTweetURL,
                        Timestamp=agent.VerificationTweetTimestamp,
                        FullText=agent.VerificationTweetText,
                    )
                    update_data = RegisteredAgentRequest(
                        HotKey=hotkey,
                        UID=str(agent.UID),
                        SubnetID=int(self.validator.netuid),
                        Version=str(4),
                        Emissions=agent_emissions,
                        VerificationTweet=verification_tweet,
                        Profile={
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
                                IsVerified=x_profile["data"]["IsVerified"],
                                Joined=x_profile["data"]["Joined"],
                                ListedCount=x_profile["data"]["ListedCount"],
                                Location=x_profile["data"]["Location"],
                                PinnedTweetIDs=x_profile["data"]["PinnedTweetIDs"],
                                TweetsCount=x_profile["data"]["TweetsCount"],
                                URL=x_profile["data"]["URL"],
                                Website=x_profile["data"]["Website"],
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
                        (
                            verified_tweet,
                            user_id,
                            screen_name,
                            avatar,
                            name,
                            is_verified,
                            followers_count,
                            error,
                        ) = await self.verify_tweet(tweet_id, node.hotkey)
                        payload = {}
                        payload["agent"] = str(screen_name)

                        if error:
                            payload["message"] = f"Failed to verify tweet: {str(error)}"
                        elif verified_tweet and user_id:
                            try:
                                await self.register_agent(
                                    node,
                                    verified_tweet,
                                    user_id,
                                    screen_name,
                                    avatar,
                                    name,
                                    is_verified,
                                    followers_count,
                                )
                                payload["message"] = "Successfully registered!"
                            except Exception as e:
                                payload["message"] = str(e)
                        elif not user_id:
                            payload["message"] = "UserId not found"
                        elif not verified_tweet:
                            payload["message"] = "Verified Tweet not found"
                        else:
                            payload["message"] = (
                                "Unknown error occured in agent registration"
                            )

                        logger.info(f"Sending payload to miner: {payload}")
                        response = await self.registration_callback(node, payload)
                        logger.info(
                            f"Miner Response from Registration Callback: {response}"
                        )

                except Exception as e:
                    logger.error(
                        f"Unknown exception occured during agent registration loop for node {
                                hotkey}: {str(e)}"
                    )

        except Exception as e:
            logger.error("Error checking registered nodes: %s", str(e))

    async def verify_tweet(
        self, id: str, hotkey: str
    ) -> tuple[VerifiedTweet, str, str, str, str, bool, int, str]:
        """Fetch tweet from Twitter API"""
        try:
            logger.info(f"Verifying tweet: {id}")
            result = TweetValidator().fetch_tweet(id)
            error = None
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
            is_verified = user.get("is_blue_verified")
            full_text = tweet_data_result.get("legacy", {}).get("full_text")
            followers_count = user.get("legacy", {}).get("followers_count")
            avatar = user.get("legacy", {}).get("profile_image_url_https")

            logger.info(
                f"Got tweet result: {
                        tweet_id} - {screen_name} **** {full_text} - {avatar}"
            )

            if not isinstance(screen_name, str) or not isinstance(full_text, str):
                error = "Invalid tweet data: screen_name or full_text is not a string"
                logger.error(error)

            # ensure hotkey is in the tweet text
            if full_text and not hotkey in full_text:
                error = f"Hotkey {hotkey} is not in the tweet text {full_text}"
                logger.error(error)

            verification_tweet = VerifiedTweet(
                TweetID=tweet_id,
                URL=f"https://twitter.com/{screen_name}/status/{tweet_id}",
                Timestamp=datetime.strptime(
                    created_at, "%a %b %d %H:%M:%S %z %Y"
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                FullText=full_text,
            )
            return (
                verification_tweet,
                user_id,
                screen_name,
                avatar,
                name,
                is_verified,
                followers_count,
                error,
            )
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return None, None, None, None, None, None, None, str(e)

    async def get_verification_tweet_id(self, node: Node) -> Optional[str]:
        endpoint = "/get_verification_tweet_id"
        try:
            return await self.validator.make_non_streamed_get(node, endpoint)
        except Exception as e:
            logger.error(f"Failed to get verification tweet id: {str(e)}")

    async def registration_callback(self, node: Node, payload: Any) -> Optional[str]:
        endpoint = "/registration_callback"
        try:
            return await self.validator.make_non_streamed_post(node, endpoint, payload)
        except Exception as e:
            logger.error(f"Failed to send registration callback: {str(e)}")

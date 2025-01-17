"""
Agent Registration Module

This module provides functionality to manage agent registration.
It handles agent registration, deregistration, profile updates, and verification processes.

Key Components:
    - ValidatorRegistration: Main class for managing agent registration operations
    - RegistrationAPIError: Custom exception for handling API-specific errors

Environment Variables:
    - API_KEY: Authentication token for the Protocol API (optional)
    - API_URL: Base URL for the API (defaults to https://test.protocol-api.masa.ai)

Usage Example:
    ```python
    # Initialize registration handler
    registration = ValidatorRegistration(validator)
    
    # Register a new agent
    await registration.register_agent(
        node=node,
        verified_tweet=tweet,
        user_id="123",
        screen_name="agent1",
        avatar="https://...",
        name="Agent One",
        is_verified=True,
        followers_count=1000
    )
    
    # Fetch registered agents
    await registration.fetch_registered_agents()
    
    # Deregister an agent
    success = await registration.deregister_agent(agent)
    ```

Note:
    All API interactions are handled asynchronously using httpx client.
    The module maintains proper error handling and logging throughout all operations.
"""

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

# Constants
DEFAULT_API_URL = "https://test.protocol-api.masa.ai"
API_VERSION = "v1.0.0"
SUBNET_API_PATH = "subnet59"

class RegistrationAPIError(Exception):
    """
    RegistrationAPIError represents errors that occur during Registration API operations.
    
    Attributes:
        status_code: Optional HTTP status code from the failed request
        response_body: Optional response body from the failed request
        message: Descriptive error message
    """
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Registration API Error: {message} " + 
                        (f"(Status: {status_code})" if status_code else "") +
                        (f" - Response: {response_body}" if response_body else ""))

class ValidatorRegistration:
    """
    ValidatorRegistration handles all agent registration operations with the Protocol API.
    
    This class manages the complete lifecycle of agent registration including:
    - Initial registration with verification
    - Deregistration of existing agents
    - Fetching currently registered agents
    - Updating agent profiles and emissions
    - Verifying registration status
    
    Attributes:
        validator: The validator instance managing the registration operations
        httpx_client: Async HTTP client for API communication
        api_url: Base URL for the Protocol API
        api_key: Authentication key for API access
    
    Example:
        registration = ValidatorRegistration(validator)
        await registration.fetch_registered_agents()
    """
    
    def __init__(self, validator: Any):
        """
        Initialize the registration handler.
        
        Args:
            validator: The validator instance to handle registration for
        """
        self.validator = validator
        self._setup_client()

    def _setup_client(self) -> None:
        """
        Initialize HTTP client with authentication headers.
        
        Uses API_KEY from environment variables if available. The client is configured
        with proper authentication headers and base URL settings.
        """
        self.api_url = os.getenv("API_URL", DEFAULT_API_URL)
        self.api_key = os.getenv("API_KEY")
        
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        logger.debug(f"Initializing Registration client with{'out' if not self.api_key else ''} API authentication")
        
        self.httpx_client = httpx.AsyncClient(
            base_url=self.api_url,
            headers=headers,
        )

    @property
    def _endpoints(self):
        """
        Define API endpoints.
        
        Returns:
            dict: Mapping of endpoint names to their URL paths
        """
        return {
            'registration': f"/{API_VERSION}/{SUBNET_API_PATH}/miners/register",
            'deregistration': f"/{API_VERSION}/{SUBNET_API_PATH}/miners/deregister",
            'active_agents': f"/{API_VERSION}/{SUBNET_API_PATH}/miners/active/{self.validator.netuid}"
        }

    async def fetch_registered_agents(self) -> None:
        """Fetch registered agents from the API"""
        try:
            response = await self.httpx_client.get(self._endpoints['active_agents'])
            
            if response.status_code == 200:
                agents = response.json() or []
                self.validator.registered_agents = {
                    agent["HotKey"]: RegisteredAgentResponse(**agent) for agent in agents
                }
                logger.info(f"Successfully fetched {len(agents)} agents for subnet {self.validator.netuid}")
                return
                
            raise RegistrationAPIError(
                message="Failed to fetch registered agents",
                status_code=response.status_code,
                response_body=response.text
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching agents: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while fetching agents: {str(e)}")

    async def register_agent(self, node: Any, verified_tweet: VerifiedTweet,
                           user_id: str, screen_name: str, avatar: str, 
                           name: str, is_verified: bool, followers_count: int) -> None:
        """Register an agent"""
        try:
            node_emissions, _ = self.validator.get_emissions(node)
            registration_data = RegisteredAgentRequest(
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
            registration_data = json.loads(json.dumps(registration_data, default=lambda o: o.__dict__))
            
            response = await self.httpx_client.post(
                self._endpoints['registration'],
                json=registration_data
            )
            
            if response.status_code == 200:
                logger.info("Successfully registered agent!")
                await self.fetch_registered_agents()
                return
                
            raise RegistrationAPIError(
                message="Failed to register agent",
                status_code=response.status_code,
                response_body=response.text
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred during registration: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during registration: {str(e)}")

    async def deregister_agent(self, agent: RegisteredAgentResponse) -> bool:
        """Deregister agent with the API"""
        try:
            response = await self.httpx_client.delete(
                f"{self._endpoints['deregistration']}/{self.validator.netuid}/{agent.UID}"
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully deregistered agent {agent.Username}!")
                await self.fetch_registered_agents()
                return True
                
            raise RegistrationAPIError(
                message=f"Failed to deregister agent {agent.Username}",
                status_code=response.status_code,
                response_body=response.text
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during deregistration: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during deregistration: {str(e)}")
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
                        self._endpoints['registration'], json=update_data
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

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
from typing import Any, Optional, Dict

from fiber.logging_utils import get_logger
from fiber.networking.models import NodeWithFernet as Node


from interfaces.types import (
    TweetVerificationResult,
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
                # Filter the fields before creating RegisteredAgentResponse objects
                self.validator.registered_agents = {}
                for agent in agents:
                    try:
                        # Only pass the fields that RegisteredAgentResponse expects
                        filtered_agent = self._filter_agent_fields(agent)
                        self.validator.registered_agents[agent["HotKey"]] = RegisteredAgentResponse(**filtered_agent)
                    except Exception as e:
                        logger.error(f"Failed to process agent data: {str(e)}, Agent data: {agent}")
                        continue
                        
                logger.info(f"Successfully fetched {len(self.validator.registered_agents)} agents for subnet {self.validator.netuid}")
                return
                
            raise RegistrationAPIError(
                message="Failed to fetch registered agents",
                status_code=response.status_code,
                response_body=response.text
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching agents: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching agents: {str(e)}")
            raise

    def _filter_agent_fields(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter agent data to only include fields expected by RegisteredAgentResponse"""
        expected_fields = {
            'ID', 'HotKey', 'UID', 'SubnetID', 'Version', 'UserID', 'Username', 
            'Avatar', 'Name', 'IsVerified', 'IsActive', 'FollowersCount',
            'VerificationTweetID', 'VerificationTweetURL', 'VerificationTweetTimestamp',
            'VerificationTweetText', 'CreatedAt', 'UpdatedAt', 'Banner', 'Biography',
            'Birthday', 'FollowingCount', 'FriendsCount', 'IsPrivate', 'Joined',
            'LikesCount', 'ListedCount', 'Location', 'PinnedTweetIDs', 'TweetsCount',
            'URL', 'Website', 'Emissions', 'Marketcap'
        }
        filtered_data = {k: v for k, v in agent_data.items() if k in expected_fields}
        
        # Add IsActive field if missing (default to True for existing agents)
        if 'IsActive' not in filtered_data:
            filtered_data['IsActive'] = True
        
        return filtered_data

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
                        verification_result = await self.verify_tweet(
                            agent.VerificationTweetID, agent.HotKey
                        )
                        username = verification_result.screen_name
                        error = verification_result.error

                        if not error:
                            x_profile = await self.validator.fetch_x_profile(username)
                            if x_profile is None:
                                logger.error(
                                    f"Failed to fetch X profile on second attempt for {username}, continuing..."
                                )
                                continue
                        else:
                            logger.error(f"Failed to verify tweet: {str(error)}")
                            continue
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch profile for {agent.Username}, continuing..."
                        )
                        continue
                try:
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
                    profile = dict(dict(x_profile).get("data", {}))
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
                                Username=profile.get("Username"),
                                Avatar=profile.get("Avatar"),
                                Banner=profile.get("Banner"),
                                Biography=profile.get("Biography"),
                                FollowersCount=profile.get("FollowersCount"),
                                FollowingCount=profile.get("FollowingCount"),
                                LikesCount=profile.get("LikesCount"),
                                Name=profile.get("Name"),
                                IsVerified=profile.get("IsBlueVerified"),
                                Joined=profile.get("Joined"),
                                ListedCount=profile.get("ListedCount"),
                                Location=profile.get("Location"),
                                PinnedTweetIDs=profile.get("PinnedTweetIDs"),
                                TweetsCount=profile.get("TweetsCount"),
                                URL=profile.get("URL"),
                                Website=profile.get("Website"),
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
                        verification_result: TweetVerificationResult = (
                            await self.verify_tweet(tweet_id, node.hotkey)
                        )
                        payload = {}
                        payload["agent"] = str(verification_result.screen_name)

                        if verification_result.error:
                            payload["message"] = (
                                f"Failed to verify tweet: {str(verification_result.error)}"
                            )
                        elif (
                            verification_result.verification_tweet
                            and verification_result.user_id
                        ):
                            try:
                                await self.register_agent(
                                    node,
                                    verification_result.verification_tweet,
                                    verification_result.user_id,
                                    verification_result.screen_name,
                                    verification_result.avatar,
                                    verification_result.name,
                                    verification_result.is_verified,
                                    verification_result.followers_count,
                                )
                                payload["message"] = "Successfully registered!"
                            except Exception as e:
                                payload["message"] = str(e)
                        elif not verification_result.user_id:
                            payload["message"] = "UserId not found"
                        elif not verification_result.verification_tweet:
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

    async def verify_tweet(self, id: str, hotkey: str) -> TweetVerificationResult:
        """Fetch tweet from Twitter API"""
        try:
            logger.info(f"Verifying tweet: {id}")
            tweet_response = await self.validator.fetch_x_tweet_by_id(id)

            if not tweet_response or tweet_response.get("recordCount", 0) == 0:
                error = f"Could not fetch tweet id {id} for node {hotkey}"
                logger.error(error)
                return TweetVerificationResult(
                    None, None, None, None, None, None, None, str(error)
                )

            tweet = tweet_response.get("data", {})
            tweet_id = tweet.get("ID")
            created_at = tweet.get("TimeParsed")
            screen_name = tweet.get("Username")
            name = tweet.get("Name")
            user_id = tweet.get("UserID")
            full_text = tweet.get("Text")
            permanent_url = tweet.get("PermanentURL")

            # ensure hotkey is in the tweet text
            if hotkey not in full_text:
                error = f"Hotkey {hotkey} is not in the tweet text {full_text}"
                logger.error(error)
                return TweetVerificationResult(
                    None, None, None, None, None, None, None, str(error)
                )

            # Fetching profile to keep the response the same
            x_profile = await self.validator.fetch_x_profile(screen_name)

            if not x_profile:
                error = f"Could not fetch profile for {screen_name}"
                logger.error(error)
                return TweetVerificationResult(
                    None, None, None, None, None, None, None, str(error)
                )

            profile = dict(dict(x_profile).get("data", {}))
            followers_count = profile.get("FollowersCount")
            avatar = profile.get("Avatar")
            is_verified = profile.get("IsBlueVerified")

            logger.info(f"Verified Tweet: {tweet_id}: {screen_name}: {full_text}")

            verification_tweet = VerifiedTweet(
                TweetID=tweet_id,
                URL=permanent_url,
                Timestamp=created_at,
                FullText=full_text,
            )
            return TweetVerificationResult(
                verification_tweet,
                user_id,
                screen_name,
                avatar,
                name,
                is_verified,
                followers_count,
                None,
            )
        except Exception as e:
            logger.error(f"Unknown error, failed to register agent: {str(e)}")
            return TweetVerificationResult(
                None, None, None, None, None, None, None, str(e)
            )

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

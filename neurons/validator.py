from dotenv import load_dotenv

import os
import json
import httpx
import asyncio
import uvicorn
import threading
from typing import Optional, Dict, Tuple, List, Any
from datetime import datetime, UTC
from neurons import version_numerical

from fiber.chain import chain_utils, interface, weights
from fiber.chain.metagraph import Metagraph
from fiber.encrypted.validator import handshake, client as vali_client
from fiber.miner.server import factory_app
from fiber.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger

from fastapi import FastAPI, Depends
from cryptography.fernet import Fernet
from masa_ai.tools.validator import TweetValidator

from protocol.data_processing.post_loader import LoadPosts
from protocol.scoring.post_scorer import PostScorer
from protocol.x.scheduler import XSearchScheduler
from protocol.x.queue import RequestQueue

from interfaces.types import (
    VerifiedTweet,
    RegisteredAgentRequest,
    RegisteredAgentResponse,
    ConnectedNode,
    Profile,
)

from neurons.miner import DecryptedPayload

logger = get_logger(__name__)


AGENT_REGISTRATION_CADENCE_SECONDS = 30
SYNC_LOOP_CADENCE_SECONDS = 30
SCORE_LOOP_CADENCE_SECONDS = 60
SET_WEIGHTS_LOOP_CADENCE_SECONDS = 300
UPDATE_PROFILE_LOOP_CADENCE_SECONDS = 3600


class AgentValidator:
    def __init__(self):
        """Initialize validator"""
        load_dotenv()

        self.wallet_name = os.getenv("VALIDATOR_WALLET_NAME", "validator")
        self.hotkey_name = os.getenv("VALIDATOR_HOTKEY_NAME", "default")
        self.port = int(os.getenv("VALIDATOR_PORT", 8081))

        self.keypair = chain_utils.load_hotkey_keypair(
            self.wallet_name, self.hotkey_name
        )

        self.netuid = int(os.getenv("NETUID", "59"))
        self.httpx_client: Optional[httpx.AsyncClient] = None

        self.subtensor_network = os.getenv("SUBTENSOR_NETWORK", "finney")
        self.subtensor_address = os.getenv(
            "SUBTENSOR_ADDRESS", "wss://entrypoint-finney.opentensor.ai:443"
        )

        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")

        self.substrate = interface.get_substrate(
            subtensor_network=self.subtensor_network,
            subtensor_address=self.subtensor_address,
        )

        self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
        self.metagraph.sync_nodes()

        # local validator state
        self.connected_nodes: Dict[str, ConnectedNode] = {}
        self.registered_agents: Dict[str, RegisteredAgentResponse] = {}

        self.queue = None
        self.scheduler = None
        self.search_terms = None
        self.scored_posts = []

        self.search_count = int(os.getenv("SCHEDULER_SEARCH_COUNT", "450"))
        self.scheduler_interval_minutes = int(
            os.getenv("SCHEDULER_INTERVAL_MINUTES", "15")
        )
        self.scheduler_batch_size = int(os.getenv("SCHEDULER_BATCH_SIZE", "100"))
        self.scheduler_priority = int(os.getenv("SCHEDULER_PRIORITY", "100"))

        self.posts_loader = LoadPosts()
        self.post_scorer = PostScorer()

    async def start(self) -> None:
        """Start the validator service"""

        try:
            self.httpx_client = httpx.AsyncClient()
            self.app = factory_app(debug=False)
            self.register_routes()

            # Start background tasks
            asyncio.create_task(self.sync_loop())  # sync loop
            asyncio.create_task(
                self.check_agents_registration_loop()
            )  # agent registration
            asyncio.create_task(self.set_weights_loop())
            asyncio.create_task(self.update_agents_profiles_and_emissions_loop())
            asyncio.create_task(self.score_loop())

            self.create_scheduler()

            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=self.port, lifespan="on"
            )
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    def node(self) -> Optional[Node]:
        try:
            nodes = self.metagraph.nodes
            node = nodes[self.keypair.ss58_address]
            return node
        except Exception as e:
            logger.error(f"Failed to get node from metagraph: {e}")
            return None

    async def fetch_registered_agents(self) -> None:
        """Fetch active agents from the API and update registered_agents"""
        try:
            headers = {"Authorization": f"Bearer {os.getenv('API_KEY')}"}
            endpoint = f"{
                self.api_url}/v1.0.0/subnet59/miners/active/{self.netuid}"
            response = await self.httpx_client.get(endpoint, headers=headers)
            if response.status_code == 200:
                active_agents = response.json()
                self.registered_agents = {
                    agent["HotKey"]: RegisteredAgentResponse(**agent)
                    for agent in active_agents
                }
                logger.info("Successfully fetched and updated active agents.")
            else:
                logger.error(
                    f"Failed to fetch active agents, status code: {
                        response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred while fetching active agents: {str(e)}")

    def create_scheduler(self) -> None:
        """Initialize the X search scheduler and request queue.

        Creates a new queue based on registered agents and starts
        the scheduler with configured parameters.
        """

        if self.search_terms is not None and len(self.search_terms):
            logger.info("Stopping scheduler...")

            self.search_terms = None
            if self.scheduler is not None:
                self.scheduler.search_terms = None
                self.scheduler = None

        logger.info("Generating queue...")

        self.queue = RequestQueue()
        self.queue.start()
        self.search_terms = self.generate_search_terms(self.registered_agents)
        logger.info("Queue generated.")

        self.scheduler = XSearchScheduler(
            request_queue=self.queue,
            interval_minutes=self.scheduler_interval_minutes,
            batch_size=self.scheduler_batch_size,
            priority=self.scheduler_priority,
            search_count=self.search_count,
        )

        self.scheduler.search_terms = self.search_terms

        def run_scheduler():
            self.scheduler.start()

        thread = threading.Thread(target=run_scheduler)
        thread.start()

    async def check_agents_registration_loop(self) -> None:
        while True:
            unregistered_nodes = []
            try:
                # Iterate over each registered node to check if it has a registered agent
                for node_hotkey in self.connected_nodes:
                    if node_hotkey not in self.registered_agents:
                        unregistered_nodes.append(node_hotkey)

                # Log the unregistered nodes
                if unregistered_nodes:
                    logger.info(
                        "Unregistered nodes found: %s",
                        ", ".join(node for node in unregistered_nodes),
                    )
                else:
                    logger.info("All nodes have registered agents.")

                for node_hotkey in unregistered_nodes:
                    try:
                        raw_nodes = self.metagraph.nodes
                        full_node = raw_nodes[node_hotkey]
                        if full_node:
                            tweet_id = await self.get_agent_tweet_id(full_node)
                            verified_tweet, user_id, screen_name, avatar = (
                                await self.verify_tweet(tweet_id, full_node.hotkey)
                            )
                            if verified_tweet and user_id:
                                await self.register_agent(
                                    full_node,
                                    verified_tweet,
                                    user_id,
                                    screen_name,
                                    avatar,
                                )
                                payload = {
                                    "registered": str(screen_name),
                                    "message": "Agent successfully registered!",
                                }
                                await self.node_registration_callback(
                                    full_node, payload
                                )
                            else:
                                payload = {
                                    "registered": "Agent failed to register",
                                    "message": f"Failed to register with tweet {tweet_id}",
                                }
                                await self.node_registration_callback(
                                    full_node, payload
                                )

                    except Exception as e:
                        logger.error(
                            f"Failed to get registration info for node {
                                node_hotkey}: {str(e)}"
                        )

                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS)
            except Exception as e:
                logger.error("Error checking registered nodes: %s", str(e))
                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS / 2)

    async def get_agent_tweet_id(self, node: Node) -> Optional[str]:
        logger.info(f"Attempting to register node {node.hotkey} agent")
        registered_node = self.connected_nodes.get(node.hotkey)

        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        registration_response = await vali_client.make_non_streamed_get(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=registered_node.symmetric_key_uuid,
            endpoint="/get_verification_tweet_id",
            validator_ss58_address=self.keypair.ss58_address,
        )

        if registration_response.status_code == 200:
            verification_tweet_id = registration_response.json()
            return verification_tweet_id
        else:
            logger.error(
                f"Failed to get registration info, status code: {
                    registration_response.status_code}"
            )
            return None

    async def node_registration_callback(
        self, node: Node, payload: DecryptedPayload
    ) -> None:
        registered_node = self.connected_nodes.get(node.hotkey)
        agent = self.registered_agents.get(node.hotkey)
        logger.info(f"Registration Callback for {agent.Username}")
        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        registration_response = await vali_client.make_non_streamed_post(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=registered_node.symmetric_key_uuid,
            endpoint="/registration_callback",
            validator_ss58_address=self.keypair.ss58_address,
            miner_ss58_address=node.hotkey,
            keypair=self.keypair,
            fernet=registered_node.fernet,
            payload=payload,
        )

        if registration_response.status_code == 200:
            logger.info("Registration Callback Success")
        else:
            logger.error(
                f"Error in registration callback: {
                    registration_response.status_code}"
            )
            return None

    def generate_search_terms(
        self, agents: Dict[str, RegisteredAgentResponse]
    ) -> List[Dict[str, Any]]:
        """Generate search terms for request queues.

        This function creates search terms for a RequestQueue instance using
        the provided agents. It prepares search queries for each agent to be
        added to the queue, ensuring that the queue is populated with the
        necessary search requests for processing.

        Args:
            agents (Dict[str, RegisteredAgentResponse]): Dictionary of agents
                containing their registration details.

        Returns:
            List[Dict[str, Any]]: A list of search terms ready for queueing.
        """
        search_terms = []
        for agent in agents.values():
            logger.info(f"Adding request to the queue for id {agent.UID}")

            search_terms.append({"query": f"to:{agent.Username}", "metadata": agent})
            search_terms.append({"query": f"from:{agent.Username}", "metadata": agent})

        return search_terms

    def get_emissions(self, node: Optional[Node]) -> Tuple[float, List[float]]:
        self.substrate = interface.get_substrate(subtensor_address=self.substrate.url)
        multiplier = 10**-9
        emissions = [
            emission * multiplier
            for emission in self.substrate.query(
                "SubtensorModule", "Emission", [self.netuid]
            ).value
        ]
        node_emissions = emissions[int(node.node_id)] if node else 0
        return node_emissions, emissions

    async def register_agent(
        self,
        node: Node,
        verified_tweet: VerifiedTweet,
        user_id: str,
        screen_name: str,
        avatar: str,
    ) -> None:
        """Register an agent"""
        node_emissions, _ = self.get_emissions(node)
        registration_data = RegisteredAgentRequest(
            hotkey=node.hotkey,
            uid=str(node.node_id),
            subnet_id=int(self.netuid),
            version=str(node.protocol),  # TODO implement versioning...
            isActive=True,
            verification_tweet=verified_tweet,
            emissions=node_emissions,
            profile={
                "data": Profile(UserID=user_id, Username=screen_name, Avatar=avatar)
            },
        )
        # prep for json
        registration_data = json.loads(
            json.dumps(registration_data, default=lambda o: o.__dict__)
        )
        endpoint = f"{self.api_url}/v1.0.0/subnet59/miners/register"
        try:
            headers = {"Authorization": f"Bearer {os.getenv('API_KEY')}"}
            response = await self.httpx_client.post(
                endpoint, json=registration_data, headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully registered agent!")
                await self.fetch_registered_agents()
            else:
                logger.error(
                    f"Failed to register agent, status code: {
                        response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent registration: {str(e)}")

    async def connect_new_nodes(self) -> None:
        """Verify node registration"""

        logger.info("Attempting nodes registration")
        try:
            nodes = dict(self.metagraph.nodes)
            nodes_list = list(nodes.values())
            # Filter to specific miners if in dev environment
            if os.getenv("ENV", "prod").lower() == "dev":
                whitelist = os.getenv("MINER_WHITELIST", "").split(",")
                nodes_list = [node for node in nodes_list if node.hotkey in whitelist]

            # Filter out already registered nodes
            available_nodes = [
                node
                for node in nodes_list
                if node.hotkey not in self.connected_nodes and node.ip != "0.0.0.0"
            ]

            logger.info(f"Found {len(available_nodes)} miners")
            for node in available_nodes:
                server_address = vali_client.construct_server_address(
                    node=node,
                    replace_with_docker_localhost=False,
                    replace_with_localhost=True,
                )
                success = await self.connect_with_miner(
                    miner_address=server_address, miner_hotkey=node.hotkey
                )
                if success:
                    logger.info(
                        f"Connected to miner: {node.hotkey}, IP: {
                            node.ip}, Port: {node.port}"
                    )
                else:
                    logger.warning(f"Failed to connect to miner {node.hotkey}")

        except Exception as e:
            logger.error("Error in registration check: %s", str(e))

    async def connect_with_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Handshake with a miner"""
        try:
            # Perform handshake with miner
            symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
                self.httpx_client, miner_address, self.keypair, miner_hotkey
            )

            logger.info(f"Handshake successful with miner {miner_hotkey}")

            if not symmetric_key_str or not symmetric_key_uuid:
                logger.error(
                    f"Failed to establish secure connection with miner {
                        miner_hotkey}"
                )
                return False

            # Store miner information
            self.connected_nodes[miner_hotkey] = ConnectedNode(
                address=miner_address,
                symmetric_key=symmetric_key_str,
                symmetric_key_uuid=symmetric_key_uuid,
                fernet=Fernet(symmetric_key_str),
            )

            return True

        except Exception as e:
            logger.error(f"Failed to connect to miner: {str(e)}")
            return False

    async def stop(self) -> None:
        """Cleanup validator resources and shutdown gracefully.

        Closes:
        - HTTP client connections
        - Server instances
        """
        if self.httpx_client:
            await self.httpx_client.close()
        if self.server:
            await self.server.stop()

    async def update_agents_profiles_and_emissions_loop(self) -> None:
        """Background task to update profiles"""
        while True:
            try:
                await self.update_agents_profiles_and_emissions()
                await asyncio.sleep(UPDATE_PROFILE_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in updating profiles: {str(e)}")
                await asyncio.sleep(UPDATE_PROFILE_LOOP_CADENCE_SECONDS / 2)

    async def set_weights_loop(self) -> None:
        """Background task to set weights"""
        while True:
            try:
                if len(self.scored_posts) > 0:
                    await self.set_weights()
                await asyncio.sleep(SET_WEIGHTS_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in setting weights: {str(e)}")
                await asyncio.sleep(SET_WEIGHTS_LOOP_CADENCE_SECONDS / 2)

    async def score_loop(self) -> None:
        """Background task to score agents"""
        while True:
            try:
                self.score_posts()
                await asyncio.sleep(SCORE_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in scoring: {str(e)}")
                await asyncio.sleep(SCORE_LOOP_CADENCE_SECONDS / 2)

    async def fetch_x_profile(self, username: str) -> Dict[str, Any]:
        queue = RequestQueue()
        response = await queue.excecute_request(
            request_type="profile", request_data={"username": username}
        )

        return response

    async def update_agents_profiles_and_emissions(self) -> None:
        _, emissions = self.get_emissions(None)
        for hotkey, agent in self.registered_agents.items():
            x_profile = await self.fetch_x_profile(agent.Username)
            logger.info(f"X Profile To Update: {x_profile}")
            if x_profile is None:
                logger.info(
                    f"Trying to refetch username for agent: {
                            agent.Username}"
                )
                verified_tweet, user_id, username, avatar = await self.verify_tweet(
                    agent.VerificationTweetID, agent.HotKey
                )
                x_profile = await self.fetch_x_profile(username)
                logger.info(f"X Profile To Update: {x_profile}")
            try:
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
                    subnet_id=int(self.netuid),
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
                endpoint = f"{self.api_url}/v1.0.0/subnet59/miners/register"
                headers = {"Authorization": f"Bearer {os.getenv('API_KEY')}"}
                response = await self.httpx_client.post(
                    endpoint, json=update_data, headers=headers
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

    async def sync_loop(self) -> None:
        """Background task to sync metagraph"""
        while True:
            try:
                await self.sync_metagraph()
                await self.connect_new_nodes()
                await self.fetch_registered_agents()
                self.scheduler.search_terms = self.generate_search_terms(
                    self.registered_agents
                )
                await asyncio.sleep(SYNC_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in sync metagraph: {str(e)}")
                await asyncio.sleep(
                    SYNC_LOOP_CADENCE_SECONDS / 2
                )  # Wait before retrying

    def score_posts(self) -> None:
        """Score posts"""
        posts = self.posts_loader.load_posts(
            subnet_id=self.netuid,
            created_at_range=(
                int(datetime.now(UTC).timestamp()) - 86400,
                int(datetime.now(UTC).timestamp()),
            ),
        )
        logger.info(f"Loaded {len(posts)} posts")
        scored_posts = self.post_scorer.score_posts(posts)
        self.scored_posts = scored_posts

    async def set_weights(self) -> None:
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
            logger.info(
                f"Need to wait {
                    wait_blocks} more blocks before setting weights"
            )
            # Assuming ~12 second block time
            wait_seconds = wait_blocks * 12
            logger.info(f"Waiting {wait_seconds} seconds...")
            await asyncio.sleep(wait_seconds)

        uids, scores = self.get_average_score()

        # Set weights with multiple attempts
        for attempt in range(3):
            try:
                success = weights.set_node_weights(
                    substrate=self.substrate,
                    keypair=self.keypair,
                    node_ids=uids,
                    node_weights=scores,
                    netuid=self.netuid,
                    validator_node_id=validator_node_id,
                    version_key=version_numerical,
                    wait_for_inclusion=False,
                    wait_for_finalization=False,
                )

                if success:
                    logger.info("✅ Successfully set weights!")
                    return
                else:
                    logger.error(f"❌ Failed to set weights on attempt {attempt + 1}")
                    await asyncio.sleep(10)  # Wait between attempts

            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                await asyncio.sleep(10)  # Wait between attempts

        logger.error("Failed to set weights after all attempts")

    def get_average_score(self) -> Tuple[List[int], List[float]]:
        uids = list(set([int(post["uid"]) for post in self.scored_posts]))
        scores_by_uid = {}
        for post in self.scored_posts:
            uid = int(post["uid"])
            if uid not in scores_by_uid:
                scores_by_uid[uid] = []
            scores_by_uid[uid].append(post["average_score"])

        average_scores = {
            uid: sum(scores) / len(scores) for uid, scores in scores_by_uid.items()
        }
        # Extract just the values from the average_scores dictionary, maintaining order of uids
        scores = [average_scores[uid] for uid in uids]
        return uids, scores

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
            return verification_tweet, user_id, screen_name, avatar
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return False

    async def sync_metagraph(self) -> None:
        """Synchronize local metagraph state with chain.

        Creates new metagraph instance if needed and syncs node data.

        Raises:
            Exception: If metagraph sync fails
        """
        try:
            self.substrate = interface.get_substrate(
                subtensor_address=self.substrate.url
            )
            self.metagraph.sync_nodes()

            metagraph_node_hotkeys = list(dict(self.metagraph.nodes).keys())
            registered_node_hotkeys = list(self.connected_nodes.keys())

            for hotkey in registered_node_hotkeys:
                if hotkey not in metagraph_node_hotkeys:
                    logger.info(
                        f"Removing node {
                            hotkey} from registered nodes"
                    )
                    del self.connected_nodes[hotkey]

                    node = self.metagraph.nodes[hotkey]
                    uid = node.node_id
                    # hotkey = node.hotkey
                    await self.deregister_agent(hotkey, uid)

                    # TODO reset local data / posts for uid to be fair to scoring

            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    async def deregister_agent(self, hotkey: str, uid: str) -> None:
        """Deregister agent with the API"""
        logger.info("Deregistering agent...")
        agent = self.registered_agents.get(hotkey, {})

        try:
            verification_tweet = VerifiedTweet(
                tweet_id=agent.VerificationTweetID,
                url=agent.VerificationTweetURL,
                timestamp=agent.VerificationTweetTimestamp,
                full_text=agent.VerificationTweetText,
            )
            deregistration_data = RegisteredAgentRequest(
                hotkey=hotkey,
                uid=str(uid),
                subnet_id=int(self.netuid),
                version=str(4),  # TODO implement versioning...
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
            endpoint = f"{self.api_url}/v1.0.0/subnet59/miners/register"
            headers = {"Authorization": f"Bearer {os.getenv('API_KEY')}"}
            response = await self.httpx_client.post(
                endpoint, json=deregistration_data, headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully deregistered agent!")
                return response.json()
            else:
                logger.error(
                    f"Failed to deregister agent, status code: {
                        response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent deregistration: {str(e)}")

    def get_self(self) -> None:
        return self

    def healthcheck(self):
        try:
            info = {
                "ss58_address": str(self.keypair.ss58_address),
                "uid": str(self.metagraph.nodes[self.keypair.ss58_address].node_id),
                "ip": str(self.metagraph.nodes[self.keypair.ss58_address].ip),
                "port": str(self.metagraph.nodes[self.keypair.ss58_address].port),
                "netuid": str(self.netuid),
                "subtensor_network": str(self.subtensor_network),
                "subtensor_address": str(self.subtensor_address),
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get validator info: {str(e)}")
            return None

    def register_routes(self) -> None:
        """Register FastAPI routes"""

        self.app.add_api_route(
            "/healthcheck",
            self.healthcheck,
            methods=["GET"],
            tags=["healthcheck"],
            dependencies=[Depends(self.get_self)],
        )

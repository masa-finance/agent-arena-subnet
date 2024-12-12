from typing import TypedDict
import httpx
from cryptography.fernet import Fernet
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from fiber.validator import client as vali_client
from fiber.validator import handshake
from fiber.miner.server import factory_app
from typing import Optional, Dict
from fiber.chain import interface
import asyncio
import time
from fastapi import FastAPI
import uvicorn
import json
import os
from masa_ai.tools.validator import TweetValidator
from fiber.chain.metagraph import Metagraph
from utils.nodes import fetch_nodes_from_substrate, filter_nodes_with_ip_and_port
from fiber.networking.models import NodeWithFernet as Node
from protocol.x.scheduler import XSearchScheduler
from x.queues import generate_queue
logger = get_logger(__name__)


class Tweet(TypedDict):
    """Type definition for Tweet data structure.

    Attributes:
        user_id (str): The Twitter user ID
        tweet_id (str): The unique tweet identifier
        url (str): The full URL to the tweet
        timestamp (str): When the tweet was created
        full_text (str): The complete text content of the tweet
    """
    user_id: str
    tweet_id: str
    url: str
    timestamp: str
    full_text: str


class RegisteredAgent(TypedDict):
    """Type definition for registered agent information.

    Attributes:
        hotkey (str): The agent's hotkey identifier
        uid (int): Unique identifier on the network
        subnet_id (int): The subnet this agent belongs to
        version (str): Agent protocol version
        isActive (bool): Whether the agent is currently active
        verification_tweet (Optional[Tweet]): Associated verification tweet data
    """
    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: Optional[Tweet]


class RegisteredMiner(TypedDict):
    """Type definition for registered miner information.

    Attributes:
        address (str): The miner's network address
        symmetric_key (str): Encryption key for secure communication
        symmetric_key_uuid (str): Unique identifier for the symmetric key
        fernet (Fernet): Fernet encryption instance
        status (str): Current miner status
        last_active (float): Timestamp of last activity
    """
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet
    status: str
    last_active: float


REGISTRATION_CHECK_CADENCE_SECONDS = 10
MINER_STATUS_CHECK_CADENCE_SECONDS = 60


class AgentValidator:
    """Validator class for managing agent registration and verification on the Bittensor subnet.

    This class handles the core validator functionality including:
    - Miner registration and connection management
    - Agent verification through Twitter
    - Status monitoring and health checks
    - Secure communication using MLTS

    Attributes:
        netuid (int): Network unique identifier
        httpx_client (Optional[httpx.AsyncClient]): Async HTTP client
        registered_miners (Dict[str, RegisteredMiner]): Currently registered miners
        registered_agents (Dict[str, RegisteredAgent]): Currently registered agents
        keypair (Optional[Keypair]): Validator's keypair for authentication
        server (Optional[factory_app]): FastAPI server instance
        queue: Request queue for X search operations
        scheduler: Scheduler for managing X search requests
        substrate: Substrate interface for chain interactions
        app (Optional[FastAPI]): FastAPI application instance
        metagraph: Network metagraph state
    """

    def __init__(self):
        """Initialize validator"""
        self.netuid = int(os.getenv("NETUID", "249"))
        self.httpx_client: Optional[httpx.AsyncClient] = None

        self.registered_miners: Dict[str, RegisteredMiner] = {}
        self.registered_agents: Dict[str, RegisteredAgent] = {}

        self.keypair = None
        self.server: Optional[factory_app] = None

        self.queue = None
        self.scheduler = None
        self.search_count = int(os.getenv("SCHEDULER_SEARCH_COUNT", "450"))
        self.scheduler_interval_minutes = int(
            os.getenv("SCHEDULER_INTERVAL_MINUTES", "15"))
        self.scheduler_batch_size = int(
            os.getenv("SCHEDULER_BATCH_SIZE", "100"))
        self.scheduler_priority = int(os.getenv("SCHEDULER_PRIORITY", "100"))

        # Get network configuration from environment
        network = os.getenv("SUBTENSOR_NETWORK", "finney")
        network_address = os.getenv("SUBTENSOR_ADDRESS")
        self.substrate = interface.get_substrate(
            subtensor_network=network, subtensor_address=network_address
        )
        self.app: Optional[FastAPI] = None
        self.metagraph = None

    async def start(self, keypair: Keypair, port: int):
        """Start the validator service.

        Args:
            keypair (Keypair): The validator's keypair for authentication
            port (int): Port number to run the validator service on

        Raises:
            Exception: If startup fails for any reason
        """
        try:
            self.keypair = keypair
            self.httpx_client = httpx.AsyncClient()

            # Create FastAPI app using standard factory
            self.app = factory_app(debug=False)

            # Add our custom routes
            self.register_routes()

            await self.sync_metagraph()

            # TODO: fetch registered agents from API

            # Start background tasks
            asyncio.create_task(self.status_check_loop())
            asyncio.create_task(self.registration_check_loop())
            asyncio.create_task(self.check_registered_nodes_agents_loop())

            # Start the FastAPI server
            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    def create_scheduler(self):
        """Initialize the X search scheduler and request queue.

        Creates a new queue based on registered agents and starts
        the scheduler with configured parameters.
        """
        logger.info("Generating queue...")
        self.queue = generate_queue(self.registered_agents)
        logger.info("Queue generated.")

        self.scheduler = XSearchScheduler(
            request_queue=self.queue,
            interval_minutes=self.scheduler_interval_minutes,
            batch_size=self.scheduler_batch_size,
            priority=self.scheduler_priority,
            search_count=self.search_count)
        self.scheduler.start()

    async def check_registered_nodes_agents_loop(self):
        """Background task to verify node registration status.

        Continuously monitors nodes to ensure they have registered agents.
        Attempts to register agents for unregistered nodes.
        """
        while True:
            unregistered_nodes = []
            try:
                # Iterate over each registered node to check if it has a registered agent
                for node in self.registered_miners:
                    if node not in self.registered_agents:
                        unregistered_nodes.append(node)
                        logger.info(
                            f"Node with hotkey {
                                node} does not have a registered agent."
                        )

                # Log the unregistered nodes
                if unregistered_nodes:
                    logger.info(
                        "Unregistered nodes found: %s",
                        ", ".join(node for node in unregistered_nodes),
                    )
                else:
                    logger.info("All nodes have registered agents.")

                for node in unregistered_nodes:
                    try:
                        nodes = await fetch_nodes_from_substrate(
                            self.substrate, self.netuid
                        )
                        full_node = next(
                            (n for n in nodes if n.hotkey == node), None)
                        if full_node:
                            await self.register_agent_for_node(full_node)
                    except Exception as e:
                        logger.error(
                            f"Failed to get registration info for node {
                                node}: {str(e)}"
                        )

                    self.create_scheduler()

                await asyncio.sleep(REGISTRATION_CHECK_CADENCE_SECONDS)
            except Exception as e:
                logger.error("Error checking registered nodes: %s", str(e))
                await asyncio.sleep(REGISTRATION_CHECK_CADENCE_SECONDS / 2)

    async def register_agent_for_node(self, node: Node):
        """Register an agent for a given node by verifying their tweet.

        Args:
            node (Node): The node object containing hotkey and network details

        Raises:
            ValueError: If verification tweet cannot be retrieved or validated
            HTTPError: If connection to miner fails
        """
        registered_miner = self.registered_miners.get(node.hotkey)

        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        registration_response = await vali_client.make_non_streamed_get(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=registered_miner.get("symmetric_key_uuid"),
            endpoint="/get_verification_tweet_id",
            validator_ss58_address=self.keypair.ss58_address,
        )

        if registration_response.status_code == 200:
            verification_tweet_id = registration_response.json()
            verified_tweet = await self.verify_tweet(verification_tweet_id)
            await self.register_agent(node, verified_tweet)
        else:
            logger.error(
                f"Failed to get registration info, status code: {
                    registration_response.status_code}"
            )

    async def register_agent(self, node: Node, verified_tweet: Dict):
        """Register an agent with the validator after tweet verification.

        Args:
            node (Node): The node object containing hotkey and network details
            verified_tweet (Dict): The verified tweet data containing user and content info

        Returns:
            Dict: The registration data for the newly registered agent

        Note:
            Registration data includes hotkey, uid, subnet_id, version, status and tweet info
        """
        registration_data = {
            "hotkey": node.hotkey,
            "uid": node.node_id,
            "subnet_id": self.netuid,
            "version": node.protocol,  # TODO implement versioning...
            "isActive": True,
            "verification_tweet": verified_tweet,
        }
        logger.info("Registration data: %s", json.dumps(registration_data))
        # TODO just to ensure this runs once for now...
        self.registered_agents[node.hotkey] = registration_data
        return registration_data

    async def registration_check_loop(self):
        """Periodically verify registration status of miners.

        Continuously runs to:
        - Fetch current miners from substrate
        - Filter based on environment settings
        - Attempt connection to unregistered miners
        - Handle registration failures

        Note:
            Runs every 60 seconds in normal operation
            Falls back to 30 second interval on errors
        """
        while True:
            try:
                miners = await fetch_nodes_from_substrate(self.substrate, self.netuid)
                for miner in miners:
                    logger.info(
                        f"Miner Hotkey: {miner.hotkey}, IP: {
                            miner.ip}, Port: {miner.port}"
                    )

                # Filter miners based on environment
                if os.getenv("ENV", "prod").lower() == "dev":
                    whitelist = os.getenv("MINER_WHITELIST", "").split(",")
                    miners = [
                        miner for miner in miners if miner.hotkey in whitelist]

                # Filter out already registered miners
                miners = [
                    miner
                    for miner in miners
                    if miner.hotkey not in self.registered_miners
                ]

                miners_found = filter_nodes_with_ip_and_port(miners)

                logger.info(
                    "Checking miners registration for: %s",
                    ", ".join(miner.hotkey for miner in miners_found),
                )

                for miner in miners_found:
                    server_address = vali_client.construct_server_address(
                        node=miner,
                        replace_with_docker_localhost=False,
                        replace_with_localhost=True,
                    )
                    success = await self.connect_to_miner(
                        miner_address=server_address, miner_hotkey=miner.hotkey
                    )
                    if success:
                        logger.info(
                            f"Successfully connected to miner {
                                miner.hotkey}"
                        )
                    else:
                        logger.warning(
                            f"Failed to connect to miner {miner.hotkey}")

                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error("Error in registration check: %s", str(e))
                await asyncio.sleep(30)

    async def connect_to_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Establish secure connection with a miner using MLTS handshake.

        Args:
            miner_address (str): Network address of the miner
            miner_hotkey (str): Miner's hotkey identifier

        Returns:
            bool: True if connection successful, False otherwise

        Note:
            Stores connection details in registered_miners on success
        """
        try:
            logger.info(f"Attempting to do handshake {
                        miner_address} - {miner_hotkey}")

            # Perform handshake with miner
            symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
                self.httpx_client, miner_address, self.keypair, miner_hotkey
            )

            logger.info("Symmetric key passes")

            if not symmetric_key_str or not symmetric_key_uuid:
                logger.error(
                    f"Failed to establish secure connection with miner {
                        miner_hotkey}"
                )
                return False

            # Store miner information
            self.registered_miners[miner_hotkey] = {
                "address": miner_address,
                "symmetric_key": symmetric_key_str,
                "symmetric_key_uuid": symmetric_key_uuid,
                "fernet": Fernet(symmetric_key_str),
                "last_active": time.time(),
                "status": "active",
            }

            logger.info(f"Connected to miner {
                        miner_hotkey} at {miner_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to miner: {str(e)}")
            return False

    async def stop(self):
        """Cleanup validator resources and shutdown gracefully.

        Closes:
        - HTTP client connections
        - Server instances
        """
        if self.httpx_client:
            await self.httpx_client.aclose()
        if self.server:
            await self.server.stop()

    async def verify_tweet(self, id: str) -> Optional[Dict[str, str]]:
        """Verify and fetch tweet data from Twitter API.

        Args:
            id (str): Twitter tweet ID to verify

        Returns:
            Optional[Dict[str, str]]: Verified tweet data if successful, None otherwise

        Raises:
            ValueError: If tweet data is invalid or hotkey not registered

        Note:
            Tweet must contain valid hotkey in full_text
        """
        try:
            result = TweetValidator().fetch_tweet(id)
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

            if not isinstance(screen_name, str) or not isinstance(full_text, str):
                msg = "Invalid tweet data: screen_name or full_text is not a string"
                logger.error(msg)
                raise ValueError(msg)

            # Ensure that the hotkey (full_text) is registered on the metagraph
            if not self.registered_miners.get(full_text):
                msg = f"Hotkey {full_text} is not registered on the metagraph"
                logger.error(msg)
                raise ValueError(msg)

            verification_tweet = {
                "user_id": user_id,  # for primary key
                "tweet_id": tweet_id,
                "url": f"https://twitter.com/{screen_name}/status/{tweet_id}",
                "timestamp": created_at,
                "full_text": full_text,
            }
            return verification_tweet
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return False

    async def check_miners_status(self):
        """Check status of all registered miners.

        Verifies:
        - Active status on metagraph
        - Recent activity (within 5 minutes)
        - Updates miner status accordingly

        Note:
            Marks miners as inactive if either check fails
        """
        try:
            await self.sync_metagraph()

            for hotkey, miner_info in self.registered_miners.items():
                try:
                    uid = miner_info.get("uid", None)

                    # Check if still active on metagraph
                    is_active = self.metagraph.active[uid].item() == 1

                    # Check last activity
                    # 5 min timeout
                    is_responsive = (
                        time.time() - miner_info["last_active"]) < 300

                    if not is_active or not is_responsive:
                        miner_info["status"] = "inactive"
                        logger.warning(f"Miner {hotkey} marked as inactive")

                except Exception as e:
                    logger.error(
                        f"Error checking miner {
                            hotkey} status: {str(e)}"
                    )
                    miner_info["status"] = "error"

        except Exception as e:
            logger.error(f"Error in miners status check: {str(e)}")

    async def status_check_loop(self):
        """Background task to periodically check miner status.

        Runs check_miners_status() at regular intervals defined by 
        MINER_STATUS_CHECK_CADENCE_SECONDS.

        Note:
            Halves check interval on errors for faster recovery
        """
        while True:
            try:
                await self.check_miners_status()
                await asyncio.sleep(MINER_STATUS_CHECK_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in status check loop: {str(e)}")
                await asyncio.sleep(
                    MINER_STATUS_CHECK_CADENCE_SECONDS / 2
                )  # Wait before retrying

    async def sync_metagraph(self):
        """Synchronize local metagraph state with chain.

        Creates new metagraph instance if needed and syncs node data.

        Raises:
            Exception: If metagraph sync fails
        """
        try:
            if self.metagraph is None:
                self.metagraph = Metagraph(
                    netuid=self.netuid, substrate=self.substrate)
            self.metagraph.sync_nodes()
            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def register_routes(self):
        """Register FastAPI routes"""

        # @self.app.post("/verify_tweet")
        # async def verify_tweet(id: str):
        #     return await self.verify_tweet(id)

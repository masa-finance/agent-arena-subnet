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
from fastapi import FastAPI
import uvicorn
import json
import os
from masa_ai.tools.validator import TweetValidator
from fiber.chain.metagraph import Metagraph
from utils.nodes import fetch_nodes_from_substrate, filter_nodes_with_ip_and_port
from fiber.networking.models import NodeWithFernet as Node

logger = get_logger(__name__)

from typing import TypedDict


class Tweet(TypedDict):
    user_id: str
    tweet_id: str
    url: str
    timestamp: str
    full_text: str


class RegisteredAgent(TypedDict):
    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: Optional[Tweet]


class RegisteredMiner(TypedDict):
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet


MINER_REGISTRATION_CADENCE_SECONDS = 10
AGENT_REGISTRATION_CADENCE_SECONDS = 10
SYNC_METAGRAPH_CADENCE_SECONDS = 60


class AgentValidator:
    def __init__(self):
        """Initialize validator"""
        self.netuid = int(os.getenv("NETUID", "249"))
        self.httpx_client: Optional[httpx.AsyncClient] = None

        self.registered_miners: Dict[str, RegisteredMiner] = {}
        self.registered_agents: Dict[str, RegisteredAgent] = {}

        self.keypair = None
        self.server: Optional[factory_app] = None

        # Get network configuration from environment
        network = os.getenv("SUBTENSOR_NETWORK", "finney")
        network_address = os.getenv("SUBTENSOR_ADDRESS")
        self.substrate = interface.get_substrate(
            subtensor_network=network, subtensor_address=network_address
        )
        self.app: Optional[FastAPI] = None
        self.metagraph = None

    async def start(self, keypair: Keypair, port: int):
        """Start the validator"""
        try:
            self.keypair = keypair
            self.httpx_client = httpx.AsyncClient()

            # Create FastAPI app using standard factory
            self.app = factory_app(debug=False)

            # Add our custom routes
            self.register_routes()

            # Start background tasks
            asyncio.create_task(self.sync_metagraph_loop())  # sync metagraph
            asyncio.create_task(self.registration_check_loop())  # encrypted handshakes
            asyncio.create_task(
                self.check_registered_nodes_agents_loop()
            )  # agent registration

            # Start the FastAPI server
            config = uvicorn.Config(self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    async def check_registered_nodes_agents_loop(self):
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
                        full_node = next((n for n in nodes if n.hotkey == node), None)
                        if full_node:
                            await self.register_agent_for_node(full_node)
                    except Exception as e:
                        logger.error(
                            f"Failed to get registration info for node {
                                    node}: {str(e)}"
                        )

                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS)
            except Exception as e:
                logger.error("Error checking registered nodes: %s", str(e))
                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS / 2)

    async def register_agent_for_node(self, node: Node):
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
                f"Failed to get registration info, status code: {registration_response.status_code}"
            )

    async def register_agent(self, node: Node, verified_tweet: Dict):
        """Register an agent"""
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
        """Periodically verify registration"""
        while True:
            try:
                miners = await fetch_nodes_from_substrate(self.substrate, self.netuid)

                # Filter to specific miners if in dev environment
                if os.getenv("ENV", "prod").lower() == "dev":
                    whitelist = os.getenv("MINER_WHITELIST", "").split(",")
                    miners = [miner for miner in miners if miner.hotkey in whitelist]

                # Filter out already registered miners
                miners = [
                    miner
                    for miner in miners
                    if miner.hotkey not in self.registered_miners
                ]

                miners_found = filter_nodes_with_ip_and_port(miners)

                for miner in miners_found:
                    server_address = vali_client.construct_server_address(
                        node=miner,
                        replace_with_docker_localhost=False,
                        replace_with_localhost=True,
                    )
                    success = await self.handshake_with_miner(
                        miner_address=server_address, miner_hotkey=miner.hotkey
                    )
                    if success:
                        logger.info(
                            f"Connected to miner: {miner.hotkey}, IP: {miner.ip}, Port: {miner.port}"
                        )
                    else:
                        logger.warning(f"Failed to connect to miner {miner.hotkey}")

                await asyncio.sleep(MINER_REGISTRATION_CADENCE_SECONDS)
            except Exception as e:
                logger.error("Error in registration check: %s", str(e))
                await asyncio.sleep(MINER_REGISTRATION_CADENCE_SECONDS / 2)

    async def handshake_with_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Handshake with a miner"""
        try:
            # Perform handshake with miner
            symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
                self.httpx_client, miner_address, self.keypair, miner_hotkey
            )

            logger.info(f"Handshake successful with miner {miner_hotkey}")

            if not symmetric_key_str or not symmetric_key_uuid:
                logger.error(
                    f"Failed to establish secure connection with miner {miner_hotkey}"
                )
                return False

            # Store miner information
            self.registered_miners[miner_hotkey] = {
                "address": miner_address,
                "symmetric_key": symmetric_key_str,
                "symmetric_key_uuid": symmetric_key_uuid,
                "fernet": Fernet(symmetric_key_str),
            }

            return True

        except Exception as e:
            logger.error(f"Failed to connect to miner: {str(e)}")
            return False

    async def stop(self):
        """Cleanup validator resources"""
        if self.httpx_client:
            await self.httpx_client.aclose()
        if self.server:
            await self.server.stop()

    async def verify_tweet(self, id: str) -> Optional[Dict[str, str]]:
        """Fetch tweet from Twitter API"""
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

    async def sync_metagraph_loop(self):
        """Background task to sync metagraph"""
        while True:
            try:
                await self.sync_metagraph()
                await asyncio.sleep(SYNC_METAGRAPH_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in sync metagraph: {str(e)}")
                await asyncio.sleep(
                    SYNC_METAGRAPH_CADENCE_SECONDS / 2
                )  # Wait before retrying

    async def sync_metagraph(self):
        """Sync the metagraph state"""
        try:
            if self.metagraph is None:
                self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
            self.metagraph.sync_nodes()
            # TODO we should update registered miners with the new metagraph state
            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def register_routes(self):
        """Register FastAPI routes"""

        # @self.app.post("/verify_tweet")
        # async def verify_tweet(id: str):
        #     return await self.verify_tweet(id)

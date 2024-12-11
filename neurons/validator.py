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
from fiber.chain.metagraph import Metagraph
from utils.nodes import format_nodes_to_dict, filter_nodes_with_ip_and_port
from utils.twitter import verify_tweet
from fiber.networking.models import NodeWithFernet as Node
from interfaces.types import VerifiedTweet, RegisteredAgent, RegisteredMiner, Profile

logger = get_logger(__name__)


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
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")

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

            # TODO: fetch registered agents from API

            # Start background tasks
            asyncio.create_task(self.sync_metagraph_loop())  # sync metagraph
            asyncio.create_task(
                self.check_agents_registration_loop()
            )  # agent registration

            # Start the FastAPI server
            config = uvicorn.Config(self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    async def check_agents_registration_loop(self):
        while True:
            unregistered_nodes = []
            try:
                # Iterate over each registered node to check if it has a registered agent
                for node_hotkey in self.registered_miners:
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
                        nodes = format_nodes_to_dict(raw_nodes)

                        full_node = next(
                            (n for n in nodes if n.hotkey == node_hotkey), None
                        )
                        if full_node:
                            tweet_id = await self.get_agent_tweet_id(full_node)

                            verified_tweet, user_id = await verify_tweet(
                                tweet_id, node_hotkey
                            )
                            if verified_tweet and user_id:
                                await self.register_agent(
                                    full_node, verified_tweet, user_id
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

    async def get_agent_tweet_id(self, node: Node):
        logger.info(f"Attempting to register node {node.hotkey} agent")
        registered_miner = self.registered_miners.get(node.hotkey)

        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        registration_response = await vali_client.make_non_streamed_get(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=registered_miner.symmetric_key_uuid,
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

    async def register_agent(
        self, node: Node, verified_tweet: VerifiedTweet, user_id: str
    ):
        """Register an agent"""
        registration_data = RegisteredAgent(
            hotkey=node.hotkey,
            uid=node.node_id,
            subnet_id=self.netuid,
            version=str(node.protocol),  # TODO implement versioning...
            isActive=True,
            verification_tweet=verified_tweet,
            profile={
                "data": Profile(
                    UserID=user_id,
                )
            },
        )
        logger.info("Registration data: %s", json.dumps(registration_data))
        # TODO just to ensure this runs once for now...
        self.registered_agents[node.hotkey] = registration_data
        return registration_data

    async def node_registration_check(self, raw_nodes: Dict[str, Node]):
        """Verify node registration"""

        logger.info("Attempting nodes registration")
        try:
            miners = format_nodes_to_dict(raw_nodes)

            # Filter to specific miners if in dev environment
            if os.getenv("ENV", "prod").lower() == "dev":
                whitelist = os.getenv("MINER_WHITELIST", "").split(",")
                miners = [miner for miner in miners if miner.hotkey in whitelist]

            # Filter out already registered miners
            miners = [
                miner for miner in miners if miner.hotkey not in self.registered_miners
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
                        f"Connected to miner: {miner.hotkey}, IP: {
                            miner.ip}, Port: {miner.port}"
                    )
                else:
                    logger.warning(f"Failed to connect to miner {miner.hotkey}")

        except Exception as e:
            logger.error("Error in registration check: %s", str(e))

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
                    f"Failed to establish secure connection with miner {
                        miner_hotkey}"
                )
                return False

            # Store miner information
            self.registered_miners[miner_hotkey] = RegisteredMiner(
                address=miner_address,
                symmetric_key=symmetric_key_str,
                symmetric_key_uuid=symmetric_key_uuid,
                fernet=Fernet(symmetric_key_str),
            )

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

            await self.node_registration_check(self.metagraph.nodes)
            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def register_routes(self):
        """Register FastAPI routes"""

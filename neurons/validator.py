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
from validator.utils import fetch_nodes_from_substrate, filter_nodes_with_ip_and_port
from fiber.networking.models import NodeWithFernet as Node

logger = get_logger(__name__)


class AgentValidator:
    def __init__(self):
        """Initialize validator"""
        self.netuid = int(os.getenv("NETUID", "1"))

        self.scoring_weights = {
            "impressions": 0.25,
            "likes": 0.25,
            "replies": 0.25,
            "followers": 0.25,
        }
        self.httpx_client: Optional[httpx.AsyncClient] = None
        # hotkey -> miner_info mapping
        self.registered_miners: Dict[str, Dict] = {}
        # hotkey -> twitter_handle mapping
        self.registered_agents: Dict[str, Dict] = {}
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

    async def start(self, keypair: Keypair, port: int = 8081):
        """Start the validator"""
        try:
            self.keypair = keypair
            self.httpx_client = httpx.AsyncClient()

            # Create FastAPI app using standard factory
            self.app = factory_app(debug=False)

            # Add our custom routes
            self.register_routes()

            # Initialize metagraph before starting server
            await self.sync_metagraph()

            logger.info(
                f"Validator started with hotkey {
                        self.keypair.ss58_address}"
            )
            logger.info(
                f"Validator started with hotkey {
                        self.keypair.ss58_address} on port {port}"
            )

            # Start background tasks
            asyncio.create_task(self.status_check_loop())
            asyncio.create_task(self.registration_check_loop())
            asyncio.create_task(self.check_registered_nodes_agents())

            # Start the FastAPI server
            config = uvicorn.Config(self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    async def check_registered_nodes_agents(self):
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
                            await self.get_agent_registration_info(full_node)
                    except Exception as e:
                        logger.error(
                            f"Failed to get registration info for node {
                                    node}: {str(e)}"
                        )

                await asyncio.sleep(10)  # Check every minute
            except Exception as e:
                logger.error("Error checking registered nodes: %s", str(e))
                await asyncio.sleep(5)

    async def get_agent_registration_info(self, node: Node):
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
            endpoint="/get_verification_tweet",
            validator_ss58_address=self.keypair.ss58_address,
        )

        if registration_response.status_code == 200:
            registration_data = registration_response.json()
            x_registration_id = registration_data.get("x_registration_id")
            verified_tweet = await self.verify_tweet(x_registration_id)
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
                for miner in miners:
                    logger.info(
                        f"Miner Hotkey: {miner.hotkey}, IP: {miner.ip}, Port: {miner.port}"
                    )

                # Filter miners based on environment
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
                        logger.warning(f"Failed to connect to miner {miner.hotkey}")

                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error("Error in registration check: %s", str(e))
                await asyncio.sleep(30)

    async def connect_to_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Connect to a miner"""
        try:

            print("Attempting to do handshake", miner_address, miner_hotkey)

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
            }

            logger.info(
                f"Connected to miner {
                        miner_hotkey} at {miner_address}"
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
                logger.error(
                    "Invalid tweet data: screen_name or full_text is not a string"
                )
                return None

            # Ensure that the hotkey (full_text) is registered on the metagraph
            if not self.registered_miners.get(full_text):
                logger.error(f"Hotkey {full_text} is not registered on the metagraph")
                return None

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
        """Periodic check of miners' status"""
        try:
            await self.sync_metagraph()

            for hotkey, miner_info in self.registered_miners.items():
                try:
                    uid = miner_info["uid"]

                    # Check if still active on metagraph
                    is_active = self.metagraph.active[uid].item() == 1

                    # Check last activity
                    # 5 min timeout
                    is_responsive = (time.time() - miner_info["last_active"]) < 300

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
        """Background task to check miners status"""
        while True:
            try:
                await self.check_miners_status()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in status check loop: {str(e)}")
                await asyncio.sleep(30)  # Wait before retrying

    async def sync_metagraph(self):
        """Sync the metagraph state"""
        try:
            if self.metagraph is None:
                self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
            self.metagraph.sync_nodes()
            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def register_routes(self):
        """Register FastAPI routes"""

        # @self.app.post("/verify_tweet")
        # async def verify_tweet(id: str):
        #     return await self.verify_tweet(id)

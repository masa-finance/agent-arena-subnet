from fiber.miner.server import factory_app
from fiber.chain import interface
from fiber.chain.metagraph import Metagraph

from typing import Optional
from fiber.logging_utils import get_logger

import json
import httpx
import os
import requests
from fastapi import Request

# from fiber.chain import interface
import uvicorn

# Import the vali_client module or object
from fastapi import FastAPI
from fiber.miner.middleware import configure_extra_logging_middleware
from fiber.chain import chain_utils, post_ip_to_chain
from dotenv import load_dotenv


logger = get_logger(__name__)


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        load_dotenv()

        # load environment variables
        self.netuid = int(os.getenv("NETUID", "59"))
        self.subtensor_network = os.getenv("SUBTENSOR_NETWORK", "finney")
        self.subtensor_address = os.getenv(
            "SUBTENSOR_ADDRESS", "wss://entrypoint-finney.opentensor.ai:443"
        )
        self.wallet_name = os.getenv("WALLET_NAME", "miner")
        self.hotkey_name = os.getenv("HOTKEY_NAME", "default")
        self.port = int(os.getenv("MINER_PORT", 8080))
        self.external_ip = self.get_external_ip()

        # initialize server
        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None
        self.httpx_client = None
        self.keypair = chain_utils.load_hotkey_keypair(
            self.wallet_name, self.hotkey_name
        )

        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")

        # initialize substrate
        self.substrate = interface.get_substrate(
            subtensor_network=self.subtensor_network,
            subtensor_address=self.subtensor_address,
        )
        self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
        self.metagraph.sync_nodes()

        self.post_ip_to_chain()

    async def start(self):
        """Start the Fiber server and register with validator"""
        try:
            # Initialize httpx client first
            self.httpx_client = httpx.AsyncClient()
            # Start Fiber server before handshake
            self.app = factory_app(debug=False)

            self.register_routes()

            # note, better logging - thanks Namoray!
            if os.getenv("ENV", "prod").lower() == "dev":
                configure_extra_logging_middleware(self.app)

            # Start the FastAPI server
            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=self.port, lifespan="on"
            )
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise

    def get_external_ip(self):
        env = os.getenv("ENV", "prod").lower()
        if env == "dev":
            # post this to chain to mark as local
            return "0.0.0.1"

        try:
            response = requests.get("https://api.ipify.org?format=json")
            response.raise_for_status()
            return response.json()["ip"]
        except requests.RequestException as e:
            logger.error(f"Failed to get external IP: {e}")

    def post_ip_to_chain(self):
        node = self.node()
        if node:
            if node.ip != self.external_ip or node.port != self.port:
                logger.info(
                    f"Posting IP / Port to Chain: Old IP: {node.ip}, Old Port: {node.port}, New IP: {self.external_ip}, New Port: {self.port}"
                )
                try:
                    coldkey_keypair_pub = chain_utils.load_coldkeypub_keypair(
                        wallet_name=self.wallet_name
                    )
                    post_ip_to_chain.post_node_ip_to_chain(
                        substrate=self.substrate,
                        keypair=self.keypair,
                        netuid=self.netuid,
                        external_ip=self.external_ip,
                        external_port=self.port,
                        coldkey_ss58_address=coldkey_keypair_pub.ss58_address,
                    )
                    # library will log success message
                except Exception as e:
                    logger.error(f"Failed to post IP to chain: {e}")
                    raise Exception("Failed to post IP / Port to chain")
            else:
                logger.info(
                    f"IP / Port already posted to chain: IP: {node.ip}, Port: {node.port}"
                )
        else:
            raise Exception("Hotkey not registered to metagraph")

    # note, requires metagraph sync
    def node(self):
        try:
            nodes = self.metagraph.nodes
            node = nodes[self.keypair.ss58_address]
            return node
        except Exception as e:
            logger.error(f"Failed to get node from metagraph: {e}")
            return None

    async def deregister_agent(self):
        """Register agent with the API"""
        my_node = self.node()

        try:
            deregistration_data = {
                "hotkey": self.keypair.ss58_address,
                "uid": str(my_node.node_id),
                "subnet_id": self.netuid,
                "version": "4",  # TODO: Implement versioning
                "isActive": False,
            }
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
                    f"Failed to register agent, status code: {response.status_code}, message: {response.text}"
                )
        except Exception as e:
            logger.error(f"Exception occurred during agent registration: {str(e)}")

    def get_verification_tweet_id(self) -> Optional[str]:
        """Get Verification Tweet ID For Agent Registration"""
        try:
            verification_tweet_id = os.getenv("TWEET_VERIFICATION_ID")
            return verification_tweet_id
        except Exception as e:
            logger.error(f"Failed to get tweet: {str(e)}")
            return None

    async def registration_callback(self, request: Request) -> Optional[str]:
        """Registration Callback"""
        try:
            payload = await request.json()
            logger.info(f"Registration Message: {payload}")
        except Exception as e:
            logger.error(f"Error in registration callback: {str(e)}")

    async def stop(self):
        """Cleanup and shutdown"""
        if self.server:
            await self.server.stop()

    def register_routes(self):

        self.app.add_api_route(
            "/get_verification_tweet_id",
            self.get_verification_tweet_id,
            methods=["GET"],
        )

        self.app.add_api_route(
            "/deregister_agent",
            self.deregister_agent,
            methods=["POST"],
        )

        self.app.add_api_route(
            "/registration_callback",
            self.registration_callback,
            methods=["POST"],
        )

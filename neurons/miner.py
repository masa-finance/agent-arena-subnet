from substrateinterface import Keypair
from fiber.miner.server import factory_app
from fiber.chain import interface
from fiber.chain.metagraph import Metagraph

from typing import Optional
import logging
import httpx
import os

# from fiber.chain import interface
import uvicorn
from utils.nodes import format_nodes_to_dict

# Import the vali_client module or object
from fastapi import FastAPI
from fiber.miner.middleware import configure_extra_logging_middleware

logger = logging.getLogger(__name__)


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        self.netuid = int(os.getenv("NETUID", "249"))
        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None
        self.httpx_client = None
        self.keypair = None
        self.api_url = os.getenv("API_URL", "https://test.protocol-api.masa.ai")

        # Get network configuration from environment
        network = os.getenv("SUBTENSOR_NETWORK", "finney")
        network_address = os.getenv("SUBTENSOR_ADDRESS")

        self.substrate = interface.get_substrate(
            subtensor_network=network, subtensor_address=network_address
        )
        self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
        self.metagraph.sync_nodes()

    async def start(self, keypair: Keypair, port: int):
        """Start the Fiber server and register with validator"""
        try:
            # Initialize httpx client first
            self.httpx_client = httpx.AsyncClient()
            self.keypair = keypair
            # Start Fiber server before handshake
            self.app = factory_app(debug=False)

            self.register_routes()

            # note, better logging - thanks Namoray!
            if os.getenv("ENV", "prod").lower() == "dev":
                configure_extra_logging_middleware(self.app)

            # Start the FastAPI server
            config = uvicorn.Config(self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise

    async def deregister_agent(self):
        """Register agent with the API"""
        my_hotkey = self.keypair.ss58_address
        my_node = next(
            (
                node
                for node in format_nodes_to_dict(self.metagraph.nodes)
                if node.hotkey == my_hotkey
            ),
            None,
        )

        try:
            deregistration_data = {
                "hotkey": self.keypair.ss58_address,
                "uid": str(my_node.node_id),
                "subnet_id": self.netuid,
                "version": "4",  # TODO: Implement versioning
                "isActive": False,
            }
            endpoint = f"{self.api_url}/v1.0.0/subnet59/miners/register"
            response = await self.httpx_client.post(endpoint, json=deregistration_data)
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

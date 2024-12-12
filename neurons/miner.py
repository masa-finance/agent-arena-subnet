from fiber.miner.server import factory_app
from fiber.chain import interface
from fiber.chain.metagraph import Metagraph

from typing import Optional
from fiber.logging_utils import get_logger

import json
import httpx
import os
import requests
import subprocess

# from fiber.chain import interface
import uvicorn
from utils.nodes import format_nodes_to_dict

# Import the vali_client module or object
from fastapi import FastAPI
from fiber.miner.middleware import configure_extra_logging_middleware
from fiber.chain import chain_utils

logger = get_logger(__name__)


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        # load environment variables
        self.netuid = int(os.getenv("NETUID", "249"))
        self.subtensor_network = os.getenv("SUBTENSOR_NETWORK", "test")
        self.subtensor_address = os.getenv(
            "SUBTENSOR_ADDRESS", "wss://test.finney.opentensor.ai:443"
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

        node = self.get_node()
        if node:
            if node.get("ip") != self.external_ip or node.get("port") != self.port:
                logger.info(
                    f"Metagraph IP: {node.get('ip')}, Metagraph Port: {node.get('port')} vs Local IP: {self.external_ip}, Local Port: {self.port}"
                )
                logger.info(f"Local IP: {self.external_ip}, Local port: {self.port}")
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
        try:
            result = subprocess.run(
                [
                    "fiber-post-ip",
                    "--netuid",
                    str(self.netuid),
                    "--external_ip",
                    str(self.external_ip),
                    "--external_port",
                    str(self.port),
                    "--subtensor.network",
                    self.subtensor_network,
                    "--wallet.name",
                    self.wallet_name,
                    "--wallet.hotkey",
                    self.hotkey_name,
                ],
                check=True,
            )

            if result.returncode != 0:
                logger.error("Failed to post IP to chain.")
                return
            # logger in subprocess will post a success message if passes...
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to post IP to chain: {e}")

    def get_node(self):
        try:
            with open("nodes.json", "r") as f:
                nodes_data = json.load(f)
                node = dict(nodes_data).get(self.keypair.ss58_address)
                if node is None:
                    logger.error(
                        f"Node with address {self.keypair.ss58_address} not found in nodes.json"
                    )
                return dict(node)
        except FileNotFoundError:
            logger.error("nodes.json file not found")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON from nodes.json")
        except Exception as e:
            logger.error(f"Unexpected error occurred while getting node: {str(e)}")
        return None

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

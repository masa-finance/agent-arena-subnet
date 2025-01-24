from dotenv import load_dotenv

import os
import httpx
import asyncio
import uvicorn
from typing import Optional, Dict, Tuple, List, Any

from fiber.chain import chain_utils, interface
from fiber.chain.metagraph import Metagraph
from fiber.encrypted.validator import handshake, client as vali_client
from fiber.miner.server import factory_app
from fiber.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger

from fastapi import FastAPI
from cryptography.fernet import Fernet

from protocol.request import Request

from interfaces.types import (
    RegisteredAgentResponse,
    ConnectedNode,
)

from validator.get_agent_posts import GetAgentPosts
from validator.weight_setter import ValidatorWeightSetter
from validator.registration import ValidatorRegistration


logger = get_logger(__name__)

BLOCKS_PER_WEIGHT_SETTING = 100
BLOCK_TIME_SECONDS = 12
TIME_PER_WEIGHT_SETTING = BLOCKS_PER_WEIGHT_SETTING * BLOCK_TIME_SECONDS

AGENT_REGISTRATION_CADENCE_SECONDS = 60  # 1 minute
SYNC_LOOP_CADENCE_SECONDS = 60  # 1 minute
SCORE_LOOP_CADENCE_SECONDS = (
    TIME_PER_WEIGHT_SETTING / 2
)  # half of a weight setting period

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

        self.substrate = interface.get_substrate(
            subtensor_network=self.subtensor_network,
            subtensor_address=self.subtensor_address,
        )

        self.metagraph = Metagraph(netuid=self.netuid, substrate=self.substrate)
        self.metagraph.sync_nodes()

        # local validator state
        self.connected_nodes: Dict[str, ConnectedNode] = {}
        self.registered_agents: Dict[str, RegisteredAgentResponse] = {}

        self.scored_posts = []

        self.posts_getter = GetAgentPosts(self.netuid)
        self.weight_setter = ValidatorWeightSetter(validator=self)

        self.registrar = ValidatorRegistration(validator=self)

    async def start(self) -> None:
        """Start the validator service"""
        try:
            self.httpx_client = httpx.AsyncClient()
            self.app = factory_app(debug=False)

            self.register_routes()

            # Start background tasks
            asyncio.create_task(self.sync_loop())
            asyncio.create_task(self.set_weights_loop())
            asyncio.create_task(self.score_loop())

            if os.getenv("API_KEY", None):
                asyncio.create_task(self.check_agents_registration_loop())
                asyncio.create_task(self.update_agents_profiles_and_emissions_loop())

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

    async def make_non_streamed_get(self, node: Node, endpoint: str) -> Optional[Any]:
        registered_node = self.connected_nodes.get(node.hotkey)
        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        response = await vali_client.make_non_streamed_get(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=registered_node.symmetric_key_uuid,
            endpoint=endpoint,
            validator_ss58_address=self.keypair.ss58_address,
        )
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                f"Error making non streamed get: {
                    response.status_code}"
            )
            return None

    async def make_non_streamed_post(
        self, node: Node, endpoint: str, payload: Any
    ) -> Optional[Any]:
        connected_node = self.connected_nodes.get(node.hotkey)
        server_address = vali_client.construct_server_address(
            node=node,
            replace_with_docker_localhost=False,
            replace_with_localhost=True,
        )
        response = await vali_client.make_non_streamed_post(
            httpx_client=self.httpx_client,
            server_address=server_address,
            symmetric_key_uuid=connected_node.symmetric_key_uuid,
            endpoint=endpoint,
            validator_ss58_address=self.keypair.ss58_address,
            miner_ss58_address=node.hotkey,
            keypair=self.keypair,
            fernet=connected_node.fernet,
            payload=payload,
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(
                f"Error making non streamed post: {
                    response.status_code}"
            )
            return None

    def get_emissions(self, node: Optional[Node]) -> Tuple[float, List[float]]:
        self.sync_substrate()
        multiplier = 10**-9
        emissions = [
            emission * multiplier
            for emission in self.substrate.query(
                "SubtensorModule", "Emission", [self.netuid]
            ).value
        ]
        node_emissions = emissions[int(node.node_id)] if node else 0
        return node_emissions, emissions

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
        if self.registrar.httpx_client:
            await self.registrar.httpx_client.close()
        if self.server:
            await self.server.stop()

    async def check_agents_registration_loop(self) -> None:
        """Background task to check agent registration"""
        while True:
            try:
                await self.registrar.check_agents_registration()
                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error checking registered agents: {str(e)}")
                await asyncio.sleep(AGENT_REGISTRATION_CADENCE_SECONDS / 2)

    async def update_agents_profiles_and_emissions_loop(self) -> None:
        """Background task to update profiles"""
        while True:
            try:
                await self.registrar.update_agents_profiles_and_emissions()
                await asyncio.sleep(UPDATE_PROFILE_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in updating profiles: {str(e)}")
                await asyncio.sleep(UPDATE_PROFILE_LOOP_CADENCE_SECONDS / 2)

    async def set_weights_loop(self) -> None:
        """Background task to set weights"""
        while True:
            try:
                if len(self.scored_posts) > 0:
                    await self.weight_setter.set_weights(self.scored_posts)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in setting weights: {str(e)}")
                await asyncio.sleep(60)

    async def score_loop(self) -> None:
        """Background task to score agents"""
        while True:
            try:
                self.scored_posts = await self.posts_getter.get()
                await asyncio.sleep(SCORE_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in scoring: {str(e)}")
                await asyncio.sleep(SCORE_LOOP_CADENCE_SECONDS / 2)

    async def fetch_x_profile(self, username: str) -> Dict[str, Any]:
        request = Request()
        response = await request.execute(data={"username": username})
        return response

    async def fetch_x_tweet_by_id(self, id: str) -> Dict[str, Any]:
        request = Request()
        response = await request.execute(data={"tweet_id": id})
        return response

    async def sync_loop(self) -> None:
        """Background task to sync metagraph"""
        while True:
            try:
                await self.registrar.fetch_registered_agents()
                await self.connect_new_nodes()
                await self.sync_metagraph()
                await asyncio.sleep(SYNC_LOOP_CADENCE_SECONDS)
            except Exception as e:
                logger.error(f"Error in sync metagraph: {str(e)}")
                await asyncio.sleep(
                    SYNC_LOOP_CADENCE_SECONDS / 2
                )  # Wait before retrying

    def sync_substrate(self) -> None:
        self.substrate = interface.get_substrate(subtensor_address=self.substrate.url)

    async def sync_metagraph(self) -> None:
        """Synchronize local metagraph state with chain"""
        try:
            self.sync_substrate()
            self.metagraph.sync_nodes()

            keys_to_delete = []
            for hotkey, _ in self.connected_nodes.items():
                if hotkey not in self.metagraph.nodes:
                    logger.info(
                        f"Hotkey: {hotkey} has been deregistered from the metagraph"
                    )
                    agent = self.registered_agents.get(hotkey)
                    keys_to_delete.append(hotkey)
                    await self.registrar.deregister_agent(agent)

            for hotkey in keys_to_delete:
                del self.connected_nodes[hotkey]

            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

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
        )

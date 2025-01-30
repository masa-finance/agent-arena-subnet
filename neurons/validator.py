from dotenv import load_dotenv

import os
import httpx
import asyncio
import uvicorn
from typing import Optional, Dict, Any

from fiber.chain import chain_utils, interface
from fiber.chain.metagraph import Metagraph
from fiber.miner.server import factory_app
from fiber.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger

from fastapi import FastAPI

from interfaces.types import (
    RegisteredAgentResponse,
    ConnectedNode,
)

from validator.posts_getter import PostsGetter
from validator.weight_setter import ValidatorWeightSetter
from validator.registration import ValidatorRegistration

from validator.config import Config
from validator.http_client import HttpClientManager
from validator.node_manager import NodeManager
from validator.background_tasks import BackgroundTasks
from validator.api_routes import register_routes
from validator.network_operations import (
    make_non_streamed_get,
    make_non_streamed_post,
)
from validator.metagraph import MetagraphManager


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

        self.config = Config()
        self.http_client_manager = HttpClientManager()

        self.keypair = chain_utils.load_hotkey_keypair(
            self.config.VALIDATOR_WALLET_NAME, self.config.VALIDATOR_HOTKEY_NAME
        )

        self.netuid = int(os.getenv("NETUID", "59"))

        self.subtensor_network = os.getenv("SUBTENSOR_NETWORK", "finney")
        self.subtensor_address = os.getenv(
            "SUBTENSOR_ADDRESS", "wss://entrypoint-finney.opentensor.ai:443"
        )

        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None

        self.substrate = interface.get_substrate(
            subtensor_network=self.config.SUBTENSOR_NETWORK,
            subtensor_address=self.config.SUBTENSOR_ADDRESS,
        )

        self.metagraph = Metagraph(netuid=self.config.NETUID, substrate=self.substrate)
        self.metagraph.sync_nodes()

        # local validator state
        self.connected_nodes: Dict[str, ConnectedNode] = {}
        self.registered_agents: Dict[str, RegisteredAgentResponse] = {}

        self.scored_posts = []

        self.posts_getter = PostsGetter(self.netuid)
        self.weight_setter = ValidatorWeightSetter(validator=self)

        self.registrar = ValidatorRegistration(validator=self)

        self.node_manager = NodeManager(validator=self)
        self.background_tasks = BackgroundTasks(validator=self)
        self.metagraph_manager = MetagraphManager(validator=self)

    async def start(self) -> None:
        """Start the validator service"""
        try:
            await self.http_client_manager.start()
            self.app = factory_app(debug=False)
            register_routes(self.app, self.healthcheck)

            # Start background tasks

            asyncio.create_task(
                self.background_tasks.sync_loop(SYNC_LOOP_CADENCE_SECONDS)
            )
            asyncio.create_task(
                self.background_tasks.set_weights_loop(self.scored_posts, 60)
            )
            asyncio.create_task(self.background_tasks.score_loop(60))

            if os.getenv("API_KEY", None):
                asyncio.create_task(
                    self.background_tasks.update_agents_profiles_and_emissions_loop(
                        3600
                    )
                )
                asyncio.create_task(
                    self.background_tasks.check_agents_registration_loop(60)
                )

            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=self.config.VALIDATOR_PORT, lifespan="on"
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
        return await make_non_streamed_get(
            httpx_client=self.http_client_manager.client,
            node=node,
            endpoint=endpoint,
            connected_nodes=self.connected_nodes,
            validator_ss58_address=self.keypair.ss58_address,
        )

    async def make_non_streamed_post(
        self, node: Node, endpoint: str, payload: Any
    ) -> Optional[Any]:
        return await make_non_streamed_post(
            httpx_client=self.http_client_manager.client,
            node=node,
            endpoint=endpoint,
            payload=payload,
            connected_nodes=self.connected_nodes,
            validator_ss58_address=self.keypair.ss58_address,
            keypair=self.keypair,
        )

    async def stop(self) -> None:
        """Cleanup validator resources and shutdown gracefully.

        Closes:
        - HTTP client connections
        - Server instances
        """
        await self.http_client_manager.stop()
        if self.server:
            await self.server.stop()

    def healthcheck(self):
        try:
            info = {
                "ss58_address": str(self.keypair.ss58_address),
                "uid": str(self.metagraph.nodes[self.keypair.ss58_address].node_id),
                "ip": str(self.metagraph.nodes[self.keypair.ss58_address].ip),
                "port": str(self.metagraph.nodes[self.keypair.ss58_address].port),
                "netuid": str(self.config.NETUID),
                "subtensor_network": str(self.config.SUBTENSOR_NETWORK),
                "subtensor_address": str(self.config.SUBTENSOR_ADDRESS),
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get validator info: {str(e)}")
            return None

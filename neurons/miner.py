from dotenv import load_dotenv

import os
import httpx
import uvicorn
import requests

from fiber.chain import chain_utils, post_ip_to_chain, interface
from fiber.chain.metagraph import Metagraph
from fiber.miner.server import factory_app
from fiber.encrypted.miner.dependencies import (
    blacklist_low_stake,
    verify_request,
)
from fiber.encrypted.miner.security.encryption import (
    decrypt_general_payload,
)
from fiber.encrypted.miner.endpoints.handshake import (
    get_public_key,
    exchange_symmetric_key,
)

from fiber.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger

from functools import partial
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, Depends


logger = get_logger(__name__)


class DecryptedPayload(BaseModel):
    registered: str
    message: Optional[str] = None


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        load_dotenv()

        self.wallet_name = os.getenv("WALLET_NAME", "miner")
        self.hotkey_name = os.getenv("HOTKEY_NAME", "default")
        self.port = int(os.getenv("MINER_PORT", 8082))
        self.external_ip = self.get_external_ip()

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

        self.post_ip_to_chain()

    async def start(self) -> None:
        """Start the miner service"""

        try:
            self.httpx_client = httpx.AsyncClient()
            self.app = factory_app(debug=False)
            self.register_routes()

            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=self.port, lifespan="on"
            )
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise

    def get_external_ip(self) -> str:
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

    def post_ip_to_chain(self) -> None:
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

    def node(self) -> Optional[Node]:
        try:
            nodes = self.metagraph.nodes
            node = nodes[self.keypair.ss58_address]
            return node
        except Exception as e:
            logger.error(f"Failed to get node from metagraph: {e}")
            return None

    def get_verification_tweet_id(self) -> Optional[str]:
        """Get Verification Tweet ID For Agent Registration"""
        try:
            verification_tweet_id = os.getenv("TWEET_VERIFICATION_ID")
            return verification_tweet_id
        except Exception as e:
            logger.error(f"Failed to get tweet: {str(e)}")
            return None

    async def stop(self) -> None:
        """Cleanup and shutdown"""
        if self.server:
            await self.server.stop()

    async def registration_callback(
        self,
        decrypted_payload: DecryptedPayload = Depends(
            partial(decrypt_general_payload, DecryptedPayload),
        ),
    ) -> None:
        """Registration Callback"""
        try:
            logger.info(f"Decrypted Payload: {decrypted_payload}")
            logger.info(f"Registration Success!")
            return {"status": "Callback received"}
        except Exception as e:
            logger.error(f"Error in registration callback: {str(e)}")
            return {"status": "Error in registration callback"}

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

        self.app.add_api_route(
            "/healthcheck",
            self.healthcheck,
            methods=["GET"],
            tags=["healthcheck"],
            dependencies=[Depends(self.get_self)],
        )

        self.app.add_api_route(
            "/public-encryption-key",
            get_public_key,
            methods=["GET"],
            tags=["encryption"],
        )

        self.app.add_api_route(
            "/exchange-symmetric-key",
            exchange_symmetric_key,
            methods=["POST"],
            tags=["encryption"],
        )

        self.app.add_api_route(
            "/get_verification_tweet_id",
            self.get_verification_tweet_id,
            methods=["GET"],
            tags=["registration"],
            dependencies=[
                Depends(self.get_self),
                Depends(blacklist_low_stake),
                # TODO is there a verify_request for get requests?
            ],
        )

        self.app.add_api_route(
            "/registration_callback",
            self.registration_callback,
            methods=["POST"],
            tags=["registration"],
            dependencies=[
                Depends(self.get_self),
                Depends(blacklist_low_stake),
                Depends(verify_request),
            ],
        )

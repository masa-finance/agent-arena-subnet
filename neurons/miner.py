from substrateinterface import Keypair
from fiber.miner.server import factory_app
from typing import Optional
import logging
import httpx
import asyncio
from cryptography.fernet import Fernet
from fiber.chain import interface
import uvicorn

# Import the vali_client module or object
from fiber.validator import client as vali_client
from fiber.validator import handshake
from fastapi import FastAPI

logger = logging.getLogger(__name__)


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None
        
        self.httpx_client = None
        self.validator_address = None
        self.fernet = None
        self.keypair = None
        self.miner_hotkey_ss58_address = None
        self.symmetric_key_uuid = None
        self.registered_with_validator = False
        self.substrate = interface.get_substrate(
            subtensor_network="finney"
        )

    async def start(
        self, keypair: Keypair, validator_address: str, miner_hotkey_ss58_address: str, port: int = 8080
    ):
        """Start the Fiber server and register with validator"""
        try:
            # Initialize httpx client first
            self.httpx_client = httpx.AsyncClient()
            self.keypair = keypair
            self.validator_address = validator_address
            self.miner_hotkey_ss58_address = miner_hotkey_ss58_address
            # Start Fiber server before handshake
            self.app = factory_app(debug=False)

            # Start the FastAPI server
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=port,
                lifespan="on"
            )
            server = uvicorn.Server(config)
            await server.serve()
        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise
             
    def register_routes(self):
        @self.app.get("/get_handle")
        async def get_handle(hotkey: str):
            return await self.get_twitter_handle(hotkey)

    async def get_twitter_handle(self, hotkey: str) -> Optional[str]:
        """Get Twitter handle for a registered agent from the validator"""
        try:
            response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=self.validator_address,
                fernet=self.fernet,
                keypair=self.keypair,
                symmetric_key_uuid=self.symmetric_key_uuid,
                payload={"hotkey": hotkey},
                endpoint="/get_twitter_handle",
            )
            return response.json().get("twitter_handle")
        except Exception as e:
            logger.error(
                f"Failed to get Twitter handle: {str(e)}"
            )
            return None

    
        
        
        
        
    async def forward_registration(self, twitter_handle: str, hotkey: str) -> bool:
        """Forward agent registration request to the validator"""
        try:
            response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=self.validator_address,
                fernet=self.fernet,
                keypair=self.keypair,
                symmetric_key_uuid=self.symmetric_key_uuid,
                payload={"twitter_handle": twitter_handle, "hotkey": hotkey},
                endpoint="/register_agent",
            )
            return response.json().get("success", False)
        except Exception as e:
            logger.error(
                f"Failed to forward registration: {str(e)}"
            )
            return False

    async def stop(self):
        """Cleanup and shutdown"""
        if self.server:
            await self.server.stop()

    async def verify_registration(self) -> bool:
        """Verify registration with validator"""
        try:
            if not self.registered_with_validator:
                return False

            # Check registration on chain
            if not self.substrate.is_hotkey_registered(
                ss58_address=self.keypair.ss58_address, netuid=self.netuid
            ):
                logger.error("Miner no longer registered on chain")
                return False

            # Ping validator to verify connection
            response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=self.validator_address,
                fernet=self.fernet,
                keypair=self.keypair,
                symmetric_key_uuid=self.symmetric_key_uuid,
                payload={"ping": True},
                endpoint="/ping",
            )

            return response.json().get("success", False)

        except Exception as e:
            logger.error(f"Failed to verify registration: {str(e)}")
            return False

    async def registration_check_loop(self):
        """Periodically verify registration"""
        while True:
            try:
                if not await self.verify_registration():
                    logger.warning(
                        "Registration invalid, attempting to re-register..."
                    )
                    # Attempt to re-register
                    await self.register_with_validator()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in registration check: {str(e)}")
                await asyncio.sleep(30)

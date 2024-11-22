from substrateinterface import Keypair
from fiber.miner.server import Server
from typing import Optional
import logging
import httpx
from cryptography.fernet import Fernet
from fiber.chain import chain_utils, interface

# Import the vali_client module or object
from fiber.validator import client as vali_client
from fiber.validator import handshake

logger = logging.getLogger(__name__)

class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        self.server: Optional[Server] = None
        self.httpx_client = None
        self.validator_address = None
        self.fernet = None
        self.keypair = None
        self.symmetric_key_uuid = None
        self.registered_with_validator = False
        self.substrate = interface.get_substrate(subtensor_network="finney")

    async def start(self, keypair: Keypair, validator_address: str, port: int = 8080):
        """Start the Fiber server and register with validator"""
        try:
            # Initialize httpx client first
            self.httpx_client = httpx.AsyncClient()
            self.keypair = keypair
            self.validator_address = validator_address

            # Start Fiber server before handshake
            self.server = Server(keypair=keypair, port=port)
            await self.server.start()

            # Perform handshake with validator first
            symmetric_key_str, self.symmetric_key_uuid = await handshake.initiate_handshake(
                keypair=self.keypair,
                httpx_client=self.httpx_client,
                validator_address=self.validator_address
            )
            
            if not symmetric_key_str or not self.symmetric_key_uuid:
                raise ValueError("Failed to establish secure connection with validator")
                
            self.fernet = Fernet(symmetric_key_str)

            # Register with validator after handshake
            registration_response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=self.validator_address,
                fernet=self.fernet,
                keypair=self.keypair,
                symmetric_key_uuid=self.symmetric_key_uuid,
                payload={
                    "miner_hotkey": self.keypair.ss58_address,
                    "port": port
                },
                endpoint="/register_miner"
            )
            
            if not registration_response.json().get('success'):
                raise ValueError("Failed to register with validator")

            self.registered_with_validator = True
            
            logger.info(f"Miner started on port {port} and registered with validator at {validator_address}")
        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise

    @Server.endpoint("/get_handle")
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
                endpoint="/get_twitter_handle"
            )
            return response.json().get('twitter_handle')
        except Exception as e:
            logger.error(f"Failed to get Twitter handle: {str(e)}")
            return None

    @Server.endpoint("/register")
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
                endpoint="/register_agent"
            )
            return response.json().get('success', False)
        except Exception as e:
            logger.error(f"Failed to forward registration: {str(e)}")
            return False

    async def stop(self):
        """Cleanup and shutdown"""
        if self.server:
            await self.server.stop()
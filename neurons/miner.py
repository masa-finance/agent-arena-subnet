from substrateinterface import Keypair
from fiber.miner.server import Server
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        self.server: Optional[Server] = None

    async def start(self, keypair: Keypair, port: int = 8080):
        """Start the Fiber server for secure validator connections"""
        try:
            self.server = Server(keypair=keypair, port=port)
            await self.server.start()
            logger.info(f"Miner started on port {port}")
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
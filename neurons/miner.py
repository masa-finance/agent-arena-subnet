from substrateinterface import Keypair
from fiber.miner.server import factory_app
from typing import Optional
import logging
import httpx
import os

# from fiber.chain import interface
import uvicorn

# Import the vali_client module or object
from fastapi import FastAPI
from fiber.miner.middleware import configure_extra_logging_middleware

logger = logging.getLogger(__name__)


class AgentMiner:
    def __init__(self):
        """Initialize miner"""
        self.server: Optional[factory_app] = None
        self.app: Optional[FastAPI] = None
        self.httpx_client = None
        self.keypair = None

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
            config = uvicorn.Config(
                self.app, host="0.0.0.0", port=port, lifespan="on")
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            logger.error(f"Failed to start miner: {str(e)}")
            raise

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

import httpx
from cryptography.fernet import Fernet
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from fiber.validator import client as vali_client
from fiber.validator import handshake
from fiber.miner.server import factory_app
from protocol.base import TwitterMetrics, TokenMetrics
from typing import Optional, Dict
from protocol.twitter import TwitterService
from fiber.chain import interface
import asyncio
import time
from fastapi import FastAPI
import uvicorn
import os
from masa_ai.tools.validator import TweetValidator
from fiber.chain.metagraph import Metagraph
from validator.utils import fetch_nodes_from_substrate, filter_nodes_with_ip_and_port
from fiber.networking.models import NodeWithFernet as Node
logger = get_logger(__name__)


class AgentValidator:
    def __init__(self):
        """Initialize validator"""
        # Get NETUID from environment (don't overwrite it)
        self.netuid = int(os.getenv("NETUID", "1"))

        self.scoring_weights = {
            'impressions': 0.25,
            'likes': 0.25,
            'replies': 0.25,
            'followers': 0.25
        }
        self.httpx_client: Optional[httpx.AsyncClient] = None
        # hotkey -> miner_info mapping
        self.registered_miners: Dict[str, Dict] = {}
        # hotkey -> twitter_handle mapping
        self.registered_agents: Dict[str, str] = {}
        self.keypair = None
        self.server: Optional[factory_app] = None

        # Get network configuration from environment
        network = os.getenv("SUBTENSOR_NETWORK", "finney")
        network_address = os.getenv("SUBTENSOR_ADDRESS")
        self.substrate = interface.get_substrate(
            subtensor_network=network,
            subtensor_address=network_address
        )
        self.netuid = int(os.getenv("NETUID", "1"))
        self.app: Optional[FastAPI] = None
        self.metagraph = None

    async def start(self, keypair: Keypair, port: int = 8081):
        """Start the validator"""
        try:
            self.keypair = keypair
            self.httpx_client = httpx.AsyncClient()

            # Create FastAPI app using standard factory
            self.app = factory_app(debug=False)

            # Add our custom routes
            self.register_routes()

            # Initialize metagraph before starting server
            await self.sync_metagraph()

            logger.info(f"Validator started with hotkey {
                        self.keypair.ss58_address}")
            logger.info(f"Validator started with hotkey {
                        self.keypair.ss58_address} on port {port}")

            # Start background tasks
            asyncio.create_task(self.status_check_loop())
            asyncio.create_task(self.registration_check_loop())

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
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    async def registration_check_loop(self):
        """Periodically verify registration"""
        while True:
            try:
                miners = await fetch_nodes_from_substrate(self.substrate, self.netuid)
                for miner in miners:
                    logger.info(f"Miner Hotkey: {miner.hotkey}, IP: {miner.ip}, Port: {miner.port}")

                # Filter miners based on environment
                if os.getenv("ENV", "prod").lower() == "dev":
                    whitelist = os.getenv("MINER_WHITELIST", "").split(",")
                    miners = [miner for miner in miners if miner.hotkey in whitelist]

                miners_found = filter_nodes_with_ip_and_port(miners)

                logger.info(
                    "Checking miners registration for: %s",
                    ", ".join(miner.hotkey for miner in miners_found)
                )

                for miner in miners_found:
                    server_address = vali_client.construct_server_address(
                        node=miner,
                        replace_with_docker_localhost=False,
                        replace_with_localhost=True,
                    )
                    success = await self.connect_to_miner(
                        miner_address=server_address,
                        miner_hotkey=miner.hotkey
                    )
                    if success:
                        logger.info(f"Successfully connected to miner {miner.hotkey}")
                    else:
                        logger.warning(
                            f"Failed to connect to miner {miner.hotkey}")

                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error("Error in registration check: %s", str(e))
                await asyncio.sleep(30)

    async def handle_get_twitter_handle(self, hotkey: str) -> Dict:
        """Handle request for getting Twitter handle"""
        try:
            twitter_handle = self.registered_agents.get(hotkey)
            return {"twitter_handle": twitter_handle}
        except Exception as e:
            logger.error(f"Error handling get_twitter_handle: {str(e)}")
            return {"twitter_handle": None}

    async def handle_register_agent(self, twitter_handle: str, hotkey: str) -> Dict:
        """Handle agent registration request"""
        try:
            success = await self.register_agent(twitter_handle, hotkey)
            return {"success": success}
        except Exception as e:
            logger.error(f"Error handling register_agent: {str(e)}")
            return {"success": False}

    async def handle_miner_registration(self, miner_hotkey: str, port: int) -> Dict:
        """Handle miner registration request"""

        try:
            # Check registration on chain
            if not await self.is_miner_registered(miner_hotkey):
                return {
                    "success": False,
                    "error": "Miner not registered or not active on subnet"
                }

            # Get UID from metagraph
            uid = self.metagraph.hotkeys.index(miner_hotkey)

            # Connect to miner
            success = await self.connect_to_miner(
                miner_address=f"http://localhost:{port}",
                miner_hotkey=miner_hotkey
            )

            if success:
                # Update miner info
                self.registered_miners[miner_hotkey].update({
                    'uid': uid,
                    'last_active': time.time(),
                    'status': 'active'
                })

            return {"success": success}

        except Exception as e:
            logger.error(f"Error registering miner: {str(e)}")
            return {"success": False}

    async def connect_to_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Connect to a miner"""
        try:

            print("Attempting to do handshake", miner_address, miner_hotkey)

            # Perform handshake with miner
            symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
                self.httpx_client,
                miner_address,
                self.keypair,
                miner_hotkey
            )

            logger.info("Symmetric key passes")

            if not symmetric_key_str or not symmetric_key_uuid:
                logger.error(f"Failed to establish secure connection with miner {
                             miner_hotkey}")
                return False

            # Store miner information
            self.registered_miners[miner_hotkey] = {
                'address': miner_address,
                'symmetric_key': symmetric_key_str,
                'symmetric_key_uuid': symmetric_key_uuid,
                'fernet': Fernet(symmetric_key_str)
            }

            logger.info(f"Connected to miner {
                        miner_hotkey} at {miner_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to miner: {str(e)}")
            return False

    async def get_agent_metrics(self, hotkey: str, miner_hotkey: str) -> Optional[TwitterMetrics]:
        """Fetch metrics directly from Twitter API"""
        logger.warning(
            "Twitter service not configured - metrics collection disabled")
        return None

    async def score_agent(self,
                          metrics: TwitterMetrics,
                          token_metrics: Optional[TokenMetrics] = None) -> float:
        """Calculate agent score based on metrics"""
        logger.warning("Scoring disabled - Twitter service not configured")
        return 0.0

    async def stop(self):
        """Cleanup validator resources"""
        if self.httpx_client:
            await self.httpx_client.aclose()
        if self.server:
            await self.server.stop()

    async def register_agent(self, twitter_handle: str, hotkey: str) -> bool:
        """Register an agent with their Twitter handle"""
        try:
            self.registered_agents[hotkey] = twitter_handle
            logger.info(f"Registered agent {
                        twitter_handle} with hotkey {hotkey}")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return False

    async def fetch_tweet(self, id: str) -> Optional[str]:
        """Fetch tweet from Twitter API"""
        result = TweetValidator().fetch_tweet(id)
        tweet_data_result = result['data']['tweetResult']['result']
        screen_name = tweet_data_result['core']['user_results']['result']['legacy']['screen_name']
        full_text = tweet_data_result['legacy']['full_text']
        logger.info(f"Tweet fetched: {screen_name} - {full_text}")
        return {"screen_name": screen_name, "full_text": full_text}

    async def get_twitter_handle(self, hotkey: str) -> Optional[str]:
        """Get Twitter handle for a registered agent"""
        return self.registered_agents.get(hotkey)

    async def is_miner_registered(self, miner_hotkey: str) -> bool:
        """Check if miner is registered on the network"""
        try:
            # Check local registration
            if miner_hotkey not in self.registered_miners:
                return False

            # Sync metagraph to get latest state
            await self.sync_metagraph()

            # Get UID from metagraph
            uid = self.metagraph.hotkeys.index(miner_hotkey)

            # Check if registered and active on metagraph
            is_registered = uid in self.metagraph.uids
            is_active = self.metagraph.active[uid].item() == 1

            return is_registered and is_active

        except ValueError:  # Hotkey not found in metagraph
            return False
        except Exception as e:
            logger.error(f"Error checking miner registration: {str(e)}")
            return False

    async def check_miners_status(self):
        """Periodic check of miners' status"""
        try:
            await self.sync_metagraph()

            for hotkey, miner_info in self.registered_miners.items():
                try:
                    uid = miner_info['uid']

                    # Check if still active on metagraph
                    is_active = self.metagraph.active[uid].item() == 1

                    # Check last activity
                    # 5 min timeout
                    is_responsive = (
                        time.time() - miner_info['last_active']) < 300

                    if not is_active or not is_responsive:
                        miner_info['status'] = 'inactive'
                        logger.warning(f"Miner {hotkey} marked as inactive")

                except Exception as e:
                    logger.error(f"Error checking miner {
                                 hotkey} status: {str(e)}")
                    miner_info['status'] = 'error'

        except Exception as e:
            logger.error(f"Error in miners status check: {str(e)}")

    async def status_check_loop(self):
        """Background task to check miners status"""
        while True:
            try:
                await self.check_miners_status()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in status check loop: {str(e)}")
                await asyncio.sleep(30)  # Wait before retrying

    async def sync_metagraph(self):
        """Sync the metagraph state"""
        try:
            if self.metagraph is None:
                self.metagraph = Metagraph(
                    netuid=self.netuid,
                    substrate=self.substrate
                )
            self.metagraph.sync_nodes()
            logger.info("Metagraph synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync metagraph: {str(e)}")

    def register_routes(self):
        """Register FastAPI routes"""
        @self.app.get("/get_twitter_handle")
        async def get_twitter_handle(hotkey: str):
            return await self.handle_get_twitter_handle(hotkey)

        @self.app.post("/register_agent")
        async def register_agent(twitter_handle: str, hotkey: str):
            return await self.handle_register_agent(twitter_handle, hotkey)

        @self.app.post("/register_miner")
        async def register_miner(miner_hotkey: str, port: int):
            return await self.handle_miner_registration(miner_hotkey, port)
        
        @self.app.post("/fetch_tweet")
        async def fetch_tweet(id: str):
            return await self.fetch_tweet(id)

import os
import httpx
from cryptography.fernet import Fernet
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from fiber.validator import client as vali_client
from fiber.validator import handshake
from fiber.miner.server import Server
from protocol.base import TwitterMetrics, TokenMetrics
from typing import Optional, Dict
from protocol.twitter import TwitterService
from fiber.chain import chain_utils, interface
import asyncio
import time

logger = get_logger(__name__)

class AgentValidator:
    def __init__(self, twitter_service: TwitterService):
        """Initialize validator"""
        self.scoring_weights = {
            'impressions': 0.25,
            'likes': 0.25,
            'replies': 0.25,
            'followers': 0.25
        }
        self.twitter_service = twitter_service
        self.httpx_client: Optional[httpx.AsyncClient] = None
        self.registered_miners: Dict[str, Dict] = {}  # hotkey -> miner_info mapping
        self.registered_agents: Dict[str, str] = {}   # hotkey -> twitter_handle mapping
        self.keypair = None
        self.server: Optional[Server] = None
        self.substrate = interface.get_substrate(subtensor_network="finney")
        self.netuid = 1  # Your subnet's netuid
        
    async def start(self, keypair: Keypair, port: int = 8081):
        """Start the validator"""
        try:
            self.keypair = keypair
            self.httpx_client = httpx.AsyncClient()
            
            # Start the validator server
            self.server = Server(keypair=keypair, port=port)
            await self.server.start()
            
            logger.info(f"Validator started with hotkey {self.keypair.ss58_address} on port {port}")
            
            # Start background tasks
            asyncio.create_task(self.status_check_loop())
            
        except Exception as e:
            logger.error(f"Failed to start validator: {str(e)}")
            raise

    @Server.endpoint("/get_twitter_handle")
    async def handle_get_twitter_handle(self, hotkey: str) -> Dict:
        """Handle request for getting Twitter handle"""
        try:
            twitter_handle = self.registered_agents.get(hotkey)
            return {"twitter_handle": twitter_handle}
        except Exception as e:
            logger.error(f"Error handling get_twitter_handle: {str(e)}")
            return {"twitter_handle": None}

    @Server.endpoint("/register_agent")
    async def handle_register_agent(self, twitter_handle: str, hotkey: str) -> Dict:
        """Handle agent registration request"""
        try:
            success = await self.register_agent(twitter_handle, hotkey)
            return {"success": success}
        except Exception as e:
            logger.error(f"Error handling register_agent: {str(e)}")
            return {"success": False}

    async def connect_to_miner(self, miner_address: str, miner_hotkey: str) -> bool:
        """Connect to a miner"""
        try:
            # Perform handshake with miner
            symmetric_key_str, symmetric_key_uuid = await handshake.perform_handshake(
                keypair=self.keypair,
                httpx_client=self.httpx_client,
                server_address=miner_address,
                miner_hotkey_ss58_address=miner_hotkey
            )
            
            if not symmetric_key_str or not symmetric_key_uuid:
                logger.error(f"Failed to establish secure connection with miner {miner_hotkey}")
                return False
                
            # Store miner information
            self.registered_miners[miner_hotkey] = {
                'address': miner_address,
                'symmetric_key': symmetric_key_str,
                'symmetric_key_uuid': symmetric_key_uuid,
                'fernet': Fernet(symmetric_key_str)
            }
            
            logger.info(f"Connected to miner {miner_hotkey} at {miner_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to miner: {str(e)}")
            return False

    async def get_agent_metrics(self, hotkey: str, miner_hotkey: str) -> Optional[TwitterMetrics]:
        """Fetch metrics directly from Twitter API"""
        try:
            miner = self.registered_miners.get(miner_hotkey)
            if not miner:
                logger.error(f"No registered miner found with hotkey {miner_hotkey}")
                return None

            # Get twitter handle from miner
            response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=miner['address'],
                fernet=miner['fernet'],
                keypair=self.keypair,
                symmetric_key_uuid=miner['symmetric_key_uuid'],
                validator_ss58_address=self.keypair.ss58_address,
                miner_ss58_address=miner_hotkey,
                payload={"hotkey": hotkey},
                endpoint="/get_handle"
            )
            
            twitter_handle = response.json().get('twitter_handle')
            if not twitter_handle:
                logger.error(f"No Twitter handle found for hotkey {hotkey}")
                return None

            # Get metrics directly from Twitter
            metrics = await self.twitter_service.get_user_metrics(twitter_handle)
            return metrics

        except Exception as e:
            logger.error(f"Failed to get metrics for agent {hotkey}: {str(e)}")
            return None

    async def score_agent(self, 
                         metrics: TwitterMetrics,
                         token_metrics: Optional[TokenMetrics] = None) -> float:
        """Calculate agent score based on metrics"""
        base_score = self.calculate_base_score(metrics)
        if token_metrics:
            multiplier = self.calculate_token_multiplier(token_metrics)
            return base_score * multiplier
        return base_score
        
    def calculate_base_score(self, metrics: TwitterMetrics) -> float:
        """Calculate base score from Twitter metrics"""
        score = 0.0
        score += metrics.impressions * self.scoring_weights['impressions']
        score += metrics.likes * self.scoring_weights['likes'] 
        score += metrics.replies * self.scoring_weights['replies']
        score += metrics.followers * self.scoring_weights['followers']
        return score

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
            logger.info(f"Registered agent {twitter_handle} with hotkey {hotkey}")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return False

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

    @Server.endpoint("/register_miner")
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
                    is_responsive = (time.time() - miner_info['last_active']) < 300  # 5 min timeout
                    
                    if not is_active or not is_responsive:
                        miner_info['status'] = 'inactive'
                        logger.warning(f"Miner {hotkey} marked as inactive")
                    
                except Exception as e:
                    logger.error(f"Error checking miner {hotkey} status: {str(e)}")
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
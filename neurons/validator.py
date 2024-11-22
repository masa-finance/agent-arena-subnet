import os
import httpx
from cryptography.fernet import Fernet
from substrateinterface import Keypair
from fiber.logging_utils import get_logger
from fiber.validator import client as vali_client
from fiber.validator import handshake
from protocol.base import TwitterMetrics, TokenMetrics
from typing import Optional, Dict
import logging
from protocol.twitter import TwitterService

logger = get_logger(__name__)

class AgentValidator:
    def __init__(self, twitter_service: TwitterService):
        """Initialize validator with scoring weights and Twitter service"""
        self.scoring_weights = {
            'impressions': 0.25,
            'likes': 0.25,
            'replies': 0.25,
            'followers': 0.25
        }
        self.twitter_service = twitter_service
        self.httpx_client: Optional[httpx.AsyncClient] = None
        self.fernet: Optional[Fernet] = None
        self.symmetric_key_uuid: Optional[str] = None
        self.keypair: Optional[Keypair] = None
        self.miner_address: Optional[str] = None
        self.registered_agents: Dict[str, str] = {}  # hotkey -> twitter_handle mapping
        
    async def start(self, keypair, miner_address: str = "http://localhost:8080"):
        """Start the validator and establish connection with miner"""
        self.httpx_client = httpx.AsyncClient()
        
        # Perform handshake with miner
        symmetric_key_str, self.symmetric_key_uuid = await handshake.perform_handshake(
            keypair=keypair,
            httpx_client=self.httpx_client,
            server_address=miner_address
        )
        
        if not symmetric_key_str or not self.symmetric_key_uuid:
            raise ValueError("Failed to establish secure connection with miner")
            
        self.fernet = Fernet(symmetric_key_str)
        logger.info("Successfully connected to miner")

    async def get_agent_metrics(self, hotkey: str) -> Optional[TwitterMetrics]:
        """Fetch metrics directly from Twitter API"""
        try:
            # Get twitter handle from miner
            response = await vali_client.make_non_streamed_post(
                httpx_client=self.httpx_client,
                server_address=self.miner_address,
                fernet=self.fernet,
                keypair=self.keypair,
                symmetric_key_uuid=self.symmetric_key_uuid,
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

    @Server.endpoint("/register_agent")
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
import os
import yaml
from pathlib import Path
from typing import Dict, Optional
from masa import Masa
from loguru import logger

class MasaProtocol:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.masa_client = self._initialize_masa()
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """Load configuration from YAML files"""
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "configs"
        
        settings_path = Path(config_path) / "settings.yaml"
        secrets_path = Path(config_path) / ".secrets.yaml"
        
        try:
            with open(settings_path) as f:
                config = yaml.safe_load(f)
            
            # Load secrets if available
            if secrets_path.exists():
                with open(secrets_path) as f:
                    secrets = yaml.safe_load(f)
                config.update(secrets)
            
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _initialize_masa(self) -> Masa:
        """Initialize Masa SDK client"""
        try:
            return Masa(
                api_key=self.config.get("masa_api_key"),
                node_url=self.config.get("masa_node_url", "http://localhost:8000")
            )
        except Exception as e:
            logger.error(f"Failed to initialize Masa client: {e}")
            raise
            
    async def search_twitter(self, query: str, max_results: int = 450):
        """Execute Twitter search through Masa Protocol"""
        try:
            results = await self.masa_client.twitter.search(
                query=query,
                max_results=min(max_results, 450)  # Enforce limit
            )
            return results
        except Exception as e:
            logger.error(f"Twitter search failed: {e}")
            raise
            
    async def list_requests(self):
        """List all pending requests"""
        try:
            return await self.masa_client.list_requests()
        except Exception as e:
            logger.error(f"Failed to list requests: {e}")
            raise
            
    async def clear_requests(self):
        """Clear all pending requests"""
        try:
            return await self.masa_client.clear_requests()
        except Exception as e:
            logger.error(f"Failed to clear requests: {e}")
            raise
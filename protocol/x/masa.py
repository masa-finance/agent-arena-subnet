from typing import Dict, Optional
from pathlib import Path
import yaml
from masa_ai import Masa as MasaSDK
from loguru import logger

class Masa:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.masa_client = self._initialize_masa()
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """Load configuration from YAML file"""
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "configs" / "x"
        
        settings_path = Path(config_path) / "settings.yaml"
        logger.debug(f"Loading configuration from: {settings_path}")
        
        try:
            with open(settings_path) as f:
                config = yaml.safe_load(f)
            return config.get('default', {}) 
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _initialize_masa(self) -> MasaSDK:
        """Initialize Masa SDK client"""
        try:
            masa = MasaSDK()
            
            # Update settings through global_settings
            for key, value in self.config.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        masa.global_settings[f"{key}.{subkey}"] = subvalue
                else:
                    masa.global_settings[key] = value
                    
            return masa
        except Exception as e:
            logger.error(f"Failed to initialize Masa client: {e}")
            raise
            
    def process_requests(self, requests=None):
        """Process requests through Masa"""
        try:
            self.masa_client.process_requests(requests)
        except Exception as e:
            logger.error(f"Failed to process requests: {e}")
            raise
            
    def list_requests(self, statuses=None):
        """List all pending requests"""
        try:
            self.masa_client.list_requests(statuses)
        except Exception as e:
            logger.error(f"Failed to list requests: {e}")
            raise
            
    def clear_requests(self, request_ids=None):
        """Clear all pending requests"""
        try:
            self.masa_client.clear_requests(request_ids)
        except Exception as e:
            logger.error(f"Failed to clear requests: {e}")
            raise
from typing import Dict, Optional
from pathlib import Path
import yaml
from masa_ai.masa import Masa as MasaSDK
from loguru import logger
from datetime import datetime, timedelta
import time
import os
import logging
from typing import List, Dict, Any

class Masa:
    def __init__(self, config_path: Optional[str] = None, base_url: Optional[str] = None, data_directory=None):
        logger.debug("Initializing Masa with custom configuration")
        self.config = self._load_config(config_path)
        
        # Override BASE_URL if provided
        if base_url:
            logger.debug(f"Overriding BASE_URL with: {base_url}")
            if 'twitter' not in self.config:
                self.config['twitter'] = {}
            self.config['twitter']['BASE_URL'] = base_url
            
        # Initialize MasaSDK only once
        self.masa_sdk = self._initialize_masa()
        
        # Set data directory
        self.data_directory = data_directory or os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(self.data_directory, exist_ok=True)
        
        # Configure logging
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """Load configuration from YAML file"""
        if not config_path:
            config_path = Path(__file__).parent.parent.parent / "configs" / "x"
        
        settings_path = Path(config_path) / "settings.yaml"
        logger.debug(f"Loading configuration from: {settings_path}")
        
        try:
            with open(settings_path) as f:
                config = yaml.safe_load(f)
            config_data = config.get('default', {})
            logger.debug(f"Loaded configuration: {config_data}")
            return config_data
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _initialize_masa(self) -> MasaSDK:
        """Initialize Masa SDK client"""
        try:
            logger.debug("Initializing MasaSDK with default settings")
            masa = MasaSDK()
            
            # Update settings through global_settings
            logger.debug("Applying custom settings:")
            for key, value in self.config.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        setting_key = f"{key}.{subkey}"
                        logger.debug(f"Setting {setting_key} = {subvalue}")
                        masa.global_settings[setting_key] = subvalue
                else:
                    logger.debug(f"Setting {key} = {value}")
                    masa.global_settings[key] = value
                    
            return masa
        except Exception as e:
            logger.error(f"Failed to initialize Masa client: {e}")
            raise
            
    def process_requests(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a list of requests
        """
        self.logger.info(f"Processing {len(requests)} requests")
        
        try:
            # Initialize request processing
            processed_requests = []
            for request in requests:
                # Format request according to MasaSDK expectations
                formatted_request = {
                    "type": request["scraper"],
                    "endpoint": request["endpoint"],
                    "priority": request.get("priority", 1),
                    "parameters": request["params"]  # Convert params to parameters
                }
                
                # Create the request object expected by MasaSDK
                request_object = {
                    "request": formatted_request,  # Nest the formatted request
                    "status": "queued",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                # Log the request object for debugging
                self.logger.debug(f"Formatted request object: {request_object}")
                
                processed_requests.append(request_object)
            
            # Log all processed requests
            self.logger.debug(f"All processed requests: {processed_requests}")
            
            # Use MasaSDK to process the requests
            try:
                sdk_response = self.masa_sdk.process_requests(processed_requests)
                self.logger.debug(f"SDK Response: {sdk_response}")
            except Exception as sdk_error:
                self.logger.error(f"SDK Error: {str(sdk_error)}")
                raise
            
            # Return response with generated IDs
            response = {
                "success": True,
                "message": f"Successfully queued {len(processed_requests)} requests",
                "requests": [
                    {
                        "id": self._generate_request_id(req["request"]),
                        **req
                    }
                    for req in processed_requests
                ]
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing requests: {str(e)}")
            self.logger.exception("Full traceback:")
            return {
                "success": False,
                "message": f"Error processing requests: {str(e)}",
                "requests": []
            }

    def _generate_request_id(self, request: Dict[str, Any]) -> str:
        """Generate a unique ID for a request"""
        import hashlib
        import json
        # Log the request being hashed
        self.logger.debug(f"Generating ID for request: {request}")
        request_str = json.dumps(request, sort_keys=True)
        return hashlib.sha256(request_str.encode()).hexdigest()
            
    def list_requests(self, statuses=None):
        """List all pending requests"""
        try:
            self.masa_sdk.list_requests(statuses)
        except Exception as e:
            logger.error(f"Failed to list requests: {e}")
            raise
            
    def clear_requests(self, request_ids=None):
        """Clear all pending requests"""
        try:
            self.masa_sdk.clear_requests(request_ids)
        except Exception as e:
            logger.error(f"Failed to clear requests: {e}")
            raise
            
    def schedule_daily_x_scrape(self, search_terms=None, collection_time="00:00", max_results=100):
        """
        Schedule daily X (Twitter) data collection for specified search terms
        
        Args:
            search_terms (list): List of search terms/queries. Supports:
                - Hashtag Search: "#hashtag"
                - Mention Search: "@username"
                - From User Search: "from:username"
                - Keyword Exclusion: "-keyword"
                - OR Operator: "term1 OR term2"
                - Geo-location Based: "geocode:latitude,longitude,radius"
                - Language-Specific: "lang:language_code"
            collection_time (str): Time to collect data in "HH:MM" format
            max_results (int): Number of results per query (max 450)
        """
        if search_terms is None:
            # Default example search terms using different operators
            search_terms = [
                "from:elonmusk",              # From user
                "#AI OR #AGI",                # Hashtags with OR
                "@naval -crypto",             # Mention with exclusion
                "AI lang:en",                 # Language-specific
                "tech geocode:37.7749,-122.4194,10mi"  # Geo-located
            ]
        
        while True:
            now = datetime.now()
            target_time = datetime.strptime(collection_time, "%H:%M").time()
            target_datetime = datetime.combine(now.date(), target_time)
            
            # If target time has passed today, schedule for tomorrow
            if now.time() > target_time:
                target_datetime += timedelta(days=1)
            
            # Wait until target time
            wait_seconds = (target_datetime - now).total_seconds()
            logger.info(f"Waiting {wait_seconds/3600:.2f} hours until next collection")
            time.sleep(wait_seconds)
            
            # Prepare requests for all search terms
            requests = [
                {
                    "scraper": "XTwitterScraper",
                    "endpoint": "data/twitter/tweets/recent",
                    "priority": 1,
                    "params": {
                        "query": term,
                        "max_results": max_results
                    }
                }
                for term in search_terms
            ]
            
            # Process requests
            try:
                self.process_requests(requests)
                logger.info("Successfully collected data for all search terms")
            except Exception as e:
                logger.error(f"Failed to collect data: {e}")
import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
from protocol.x.errors import (
    handle_request_error,
    handle_response_error,
    handle_json_error,
    format_response
)

# Load environment variables
load_dotenv()

# Get environment variables with fallbacks
DEFAULT_BASE_URL = os.getenv('MASA_BASE_URL', "http://localhost:8080")
DEFAULT_API_BASE = os.getenv('MASA_API_PATH', "/api/v1/data")
DEFAULT_API_PATH = f"{DEFAULT_API_BASE}/twitter/profile"

def get_x_profile(
    username: str,
    base_url: str = DEFAULT_BASE_URL,
    api_path: str = DEFAULT_API_PATH,
    additional_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a GET request to the Masa API endpoint to fetch a Twitter profile.
    
    Args:
        username (str): The Twitter username to fetch (without @ symbol)
        base_url (str): The base URL of the API (default: "http://localhost:8080")
        api_path (str): The API endpoint path (default: "/api/v1/data/twitter/profile")
        additional_params (Dict[str, Any], optional): Additional parameters to include in the request
        
    Returns:
        Dict[str, Any]: The JSON response from the API with structure:
            {
                "data": Dict | None,  # Profile data or None if not found
                "recordCount": int    # 1 if profile found, 0 if not
            }
        
    Raises:
        requests.exceptions.RequestException: If the request fails
    """
    
    # Construct full URL
    api_url = f"{base_url.rstrip('/')}/{api_path.lstrip('/')}/{username}"
    
    # Prepare headers
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Add any additional parameters if provided
    params = additional_params if additional_params else {}
    
    try:
        # Send GET request
        response = requests.get(
            api_url,
            headers=headers,
            params=params
        )
        
        try:
            response.raise_for_status()
            response_data = response.json()
            return format_response(response_data)

        except requests.exceptions.HTTPError:
            handle_response_error(response)

    except requests.exceptions.RequestException as e:
        handle_request_error(e)
    except json.JSONDecodeError as e:
        handle_json_error(e, response.text)
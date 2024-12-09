import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get environment variables with fallbacks
DEFAULT_BASE_URL = os.getenv('MASA_BASE_URL', "http://localhost:8080")
DEFAULT_API_PATH = os.getenv('MASA_API_PATH', "/api/v1/data/twitter/tweets/recent")

def search_x(
    base_url: str = DEFAULT_BASE_URL,
    api_path: str = DEFAULT_API_PATH,
    query: str = "#Bitcoin",
    count: int = 10,
    additional_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a POST request to the Masa API endpoint to search recent tweets.
    
    Args:
        base_url (str): The base URL of the API (default: "http://localhost:8080")
        api_path (str): The API endpoint path (default: "/api/v1/data/twitter/tweets/recent")
        query (str): The search query (default: "#Bitcoin")
        count (int): Number of tweets to retrieve (default: 10)
        additional_params (Dict[str, Any], optional): Additional parameters to include in the request
        
    Returns:
        Dict[str, Any]: The JSON response from the API
        
    Raises:
        requests.exceptions.RequestException: If the request fails
    """
    
    # Construct full URL
    api_url = f"{base_url.rstrip('/')}/{api_path.lstrip('/')}"
    
    # Prepare headers
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Prepare request body
    body = {
        "query": query,
        "count": count
    }
    
    # Add any additional parameters if provided
    if additional_params:
        body.update(additional_params)
    
    try:
        # Send POST request
        response = requests.post(
            api_url,
            headers=headers,
            json=body
        )
        
        # Try to get detailed error message from response
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_response = response.json()
                error_detail = f": {json.dumps(error_response, indent=2)}"
            except json.JSONDecodeError:
                error_detail = f": {response.text}"
            
            raise Exception(
                f"API request failed with status {response.status_code}{error_detail}"
            ) from e
        
        # Return JSON response
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # Handle connection errors (timeout, DNS failure, etc.)
        raise Exception(f"Failed to connect to API: {str(e)}")
    except json.JSONDecodeError as e:
        # Handle invalid JSON in successful response
        raise Exception(f"Invalid JSON in API response: {str(e)}\nResponse text: {response.text}")

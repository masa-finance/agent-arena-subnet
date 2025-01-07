import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get environment variables with fallbacks
DEFAULT_BASE_URL = os.getenv("MASA_BASE_URL", "http://localhost:8080")
DEFAULT_API_BASE = os.getenv("MASA_API_PATH", "/api/v1/data")
DEFAULT_API_PATH = f"{DEFAULT_API_BASE}/twitter/tweets/recent"
SCHEDULER_SEARCH_COUNT = int(os.getenv("SCHEDULER_SEARCH_COUNT", 10))


def search_x(
    base_url: str = DEFAULT_BASE_URL,
    api_path: str = DEFAULT_API_PATH,
    query: str = "#Bitcoin",
    count: int = SCHEDULER_SEARCH_COUNT,
    additional_params: Optional[Dict[str, Any]] = None,
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
        Dict[str, Any]: The JSON response from the API with structure:
            {
                "data": List[Dict] | None,
                "recordCount": int
            }

    Raises:
        requests.exceptions.RequestException: If the request fails
    """

    # Construct full URL
    api_url = f"{base_url.rstrip('/')}/{api_path.lstrip('/')}"

    # Prepare headers
    headers = {"accept": "application/json", "Content-Type": "application/json"}

    # Prepare request body
    body = {"query": query, "count": count}

    # Add any additional parameters if provided
    if additional_params:
        body.update(additional_params)

    try:
        # Send POST request
        response = requests.post(api_url, headers=headers, json=body)
        
        # Parse response regardless of status code
        response_data = response.json()
        
        # Handle "No data returned" response
        if response_data.get("error") == "No data returned":
            return {
                "data": [],
                "recordCount": 0,
                "workerPeerId": response_data.get("workerPeerId")
            }

        # Handle other error status codes
        response.raise_for_status()
        
        # Ensure consistent response structure
        if response_data is None:
            return {"data": [], "recordCount": 0}

        # If data is missing or None, ensure it's properly structured
        if "data" not in response_data or response_data["data"] is None:
            response_data["data"] = []
            response_data["recordCount"] = 0
        else:
            # Update recordCount based on actual data length
            response_data["recordCount"] = len(response_data["data"])

        return response_data

    except requests.exceptions.RequestException as e:
        # Handle connection errors (timeout, DNS failure, etc.)
        raise Exception(f"Failed to connect to API: {str(e)}")
    except json.JSONDecodeError as e:
        # Handle invalid JSON in successful response
        raise Exception(
            f"Invalid JSON in API response: {
                        str(e)}\nResponse text: {response.text}"
        )

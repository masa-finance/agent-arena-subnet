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

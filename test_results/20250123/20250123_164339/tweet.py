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
DEFAULT_TWEET_API_PATH = f"{DEFAULT_API_BASE}/twitter/tweets"


def get_x_tweet_by_id(
    tweet_id: str,
    base_url: str = DEFAULT_BASE_URL,
    api_path: str = DEFAULT_TWEET_API_PATH,
    additional_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send a GET request to the Masa API endpoint to fetch a Twitter tweet by ID.

    Args:
        tweet_id (str): The Twitter tweet ID to fetch
        base_url (str): The base URL of the API (default: "http://localhost:8080")
        api_path (str): The API endpoint path (default: "/api/v1/data/twitter/tweets")
        additional_params (Dict[str, Any], optional): Additional parameters to include in the request

    Returns:
        Dict[str, Any]: The JSON response from the API with structure:
            {
                "data": Dict | None,  # Tweet data or None if not found
                "recordCount": int    # 1 if tweet found, 0 if not
            }

    Raises:
        requests.exceptions.RequestException: If the request fails
    """

    # Construct full URL
    api_url = f"{base_url.rstrip('/')}/{api_path.lstrip('/')}/{tweet_id}"

    # Prepare headers
    headers = {"accept": "application/json", "Content-Type": "application/json"}

    # Add any additional parameters if provided
    params = additional_params if additional_params else {}

    try:
        # Send GET request
        response = requests.post(api_url, headers=headers, params=params)

        # Try to get detailed error message from response
        try:
            response.raise_for_status()

            # Parse response
            response_data = response.json()

            # Ensure consistent response structure
            if response_data is None:
                return {"data": None, "recordCount": 0}

            # If data is missing or None, ensure it's properly structured
            if "data" not in response_data or response_data["data"] is None:
                response_data["data"] = None
                response_data["recordCount"] = 0
            else:
                # Set recordCount to 1 since this is a single tweet
                response_data["recordCount"] = 1

            return response_data

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

    except requests.exceptions.RequestException as e:
        # Handle connection errors (timeout, DNS failure, etc.)
        raise Exception(f"Failed to connect to API: {str(e)}")
    except json.JSONDecodeError as e:
        # Handle invalid JSON in successful response
        raise Exception(
            f"Invalid JSON in API response: {str(e)}\nResponse text: {response.text}"
        )

from typing import Dict, Any
import json
import requests
import logging

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base exception class for API related errors"""
    pass

class RequestError(APIError):
    """Exception raised for errors in the API request"""
    pass

class ResponseError(APIError):
    """Exception raised for errors in the API response"""
    pass

class JSONError(APIError):
    """Exception raised for JSON parsing errors"""
    pass

class NoDataError(APIError):
    """Exception raised when no data is found"""
    pass

class NonRetryableError(APIError):
    """Exception for errors that should not be retried (like 404s)"""
    pass

def handle_request_error(e: requests.exceptions.RequestException) -> None:
    """Handle connection errors (timeout, DNS failure, etc.)"""
    raise RequestError(f"Failed to connect to API: {str(e)}")

def handle_response_error(response: requests.Response) -> Dict[str, Any]:
    """Handle HTTP error responses with detailed error messages"""
    if response.status_code == 404:
        try:
            error_response = response.json()
            if error_response.get("error") == "No data returned":
                logger.info("No data returned from API")
                return {"data": None, "recordCount": 0}
        except json.JSONDecodeError:
            pass
    
    # Raise different exceptions based on status code
    if response.status_code == 404:
        raise NonRetryableError(f"Resource not found: {response.url}")
    
    error_detail = ""
    try:
        error_response = response.json()
        error_detail = f": {json.dumps(error_response, indent=2)}"
    except json.JSONDecodeError:
        error_detail = f": {response.text}"
    
    raise ResponseError(f"API request failed with status {response.status_code}{error_detail}")

def handle_json_error(e: json.JSONDecodeError, response_text: str) -> None:
    """Handle JSON parsing errors"""
    raise JSONError(f"Invalid JSON in API response: {str(e)}\nResponse text: {response_text}")

def format_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format API response to ensure consistent structure"""
    if response_data is None or "error" in response_data:
        logger.info(f"No data in response: {response_data}")
        return {"data": None, "recordCount": 0}
    
    if "data" not in response_data or response_data["data"] is None:
        response_data["data"] = None
        response_data["recordCount"] = 0
    
    return response_data 

def handle_response_error(response: requests.Response) -> Dict[str, Any]:
    """Handle HTTP error responses with detailed error messages"""
    if response.status_code == 404:
        try:
            error_response = response.json()
            if error_response.get("error") == "No data returned":
                logger.info("No data returned from API")
                return {"data": None, "recordCount": 0}
        except json.JSONDecodeError:
            pass
    
    # Raise different exceptions based on status code
    if response.status_code == 404:
        raise NonRetryableError(f"Resource not found: {response.url}")
    
    error_detail = ""
    try:
        error_response = response.json()
        error_detail = f": {json.dumps(error_response, indent=2)}"
    except json.JSONDecodeError:
        error_detail = f": {response.text}"
    
    raise ResponseError(f"API request failed with status {response.status_code}{error_detail}") 
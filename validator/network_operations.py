import httpx
from typing import Optional, Any
from fiber.encrypted.validator import client as vali_client
from fiber.logging_utils import get_logger
from fiber.networking.models import NodeWithFernet as Node

logger = get_logger(__name__)


async def make_non_streamed_get(
    httpx_client: httpx.AsyncClient,
    node: Node,
    endpoint: str,
    connected_nodes: dict,
    validator_ss58_address: str,
) -> Optional[Any]:
    """
    Make a non-streamed GET request to a node.

    :param httpx_client: The HTTP client to use for the request.
    :param node: The node to send the request to.
    :param endpoint: The endpoint to request.
    :param connected_nodes: A dictionary of connected nodes.
    :param validator_ss58_address: The validator's SS58 address.
    :return: The response JSON if successful, None otherwise.
    """
    registered_node = connected_nodes.get(node.hotkey)
    server_address = vali_client.construct_server_address(
        node=node,
        replace_with_docker_localhost=False,
        replace_with_localhost=True,
    )
    response = await vali_client.make_non_streamed_get(
        httpx_client=httpx_client,
        server_address=server_address,
        symmetric_key_uuid=registered_node.symmetric_key_uuid,
        endpoint=endpoint,
        validator_ss58_address=validator_ss58_address,
    )
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error making non-streamed GET: {response.status_code}")
        return None


async def make_non_streamed_post(
    httpx_client: httpx.AsyncClient,
    node: Node,
    endpoint: str,
    payload: Any,
    connected_nodes: dict,
    validator_ss58_address: str,
    keypair: Any,
) -> Optional[Any]:
    """
    Make a non-streamed POST request to a node.

    :param httpx_client: The HTTP client to use for the request.
    :param node: The node to send the request to.
    :param endpoint: The endpoint to request.
    :param payload: The payload to send in the POST request.
    :param connected_nodes: A dictionary of connected nodes.
    :param validator_ss58_address: The validator's SS58 address.
    :param keypair: The keypair used for the request.
    :return: The response JSON if successful, None otherwise.
    """
    connected_node = connected_nodes.get(node.hotkey)
    server_address = vali_client.construct_server_address(
        node=node,
        replace_with_docker_localhost=False,
        replace_with_localhost=True,
    )
    response = await vali_client.make_non_streamed_post(
        httpx_client=httpx_client,
        server_address=server_address,
        symmetric_key_uuid=connected_node.symmetric_key_uuid,
        endpoint=endpoint,
        validator_ss58_address=validator_ss58_address,
        miner_ss58_address=node.hotkey,
        keypair=keypair,
        fernet=connected_node.fernet,
        payload=payload,
    )

    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Error making non-streamed POST: {response.status_code}")
        return None

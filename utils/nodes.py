import asyncio

from fiber.chain import fetch_nodes
from fiber.chain import interface

from fiber.networking.models import NodeWithFernet as Node
from fiber.logging_utils import get_logger
logger = get_logger(__name__)


async def fetch_nodes_from_substrate(substrate: interface, netuid: int) -> list[Node]:
    logger.info("Fetching miner nodes")
    raw_nodes = await asyncio.to_thread(
        fetch_nodes.get_nodes_for_netuid, substrate, netuid
    )    
    nodes = [Node(**node.model_dump(mode="json")) for node in raw_nodes]

    return nodes


def filter_nodes_with_ip_and_port(nodes: list[Node]) -> list[Node]:
    """Filter nodes that have both IP and port defined."""
    filtered_nodes = [node for node in nodes if node.ip and node.port]
    return filtered_nodes

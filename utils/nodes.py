import asyncio
from fiber.chain import fetch_nodes, interface
from fiber.networking.models import NodeWithFernet as Node


async def fetch_nodes_from_substrate(substrate: interface, netuid: int) -> list[Node]:
    raw_nodes = await asyncio.to_thread(
        fetch_nodes.get_nodes_for_netuid, substrate, netuid
    )
    nodes = [Node(**node.model_dump(mode="json")) for node in raw_nodes]
    return nodes


def filter_nodes_with_ip_and_port(nodes: list[Node]) -> list[Node]:
    """Filter nodes that have both IP and port defined."""
    filtered_nodes = [node for node in nodes if node.ip != "0.0.0.0" and node.port != 0]
    return filtered_nodes

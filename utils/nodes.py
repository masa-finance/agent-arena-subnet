from fiber.networking.models import NodeWithFernet as Node
from typing import Dict


def format_nodes_to_dict(raw_nodes: Dict[str, Node]) -> list[Node]:
    nodes = [Node(**node.__dict__) for node in raw_nodes.values()]
    return nodes


def filter_nodes_with_ip_and_port(nodes: list[Node]) -> list[Node]:
    """Filter nodes that have both IP and port defined."""
    filtered_nodes = [node for node in nodes if node.ip != "0.0.0.0" and node.port != 0]
    return filtered_nodes

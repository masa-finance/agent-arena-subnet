"""Configuration mappings for the project."""

import os

# Mapping of mainnet subnet IDs to their corresponding testnet IDs
SUBNET_MAPPINGS = {
    # Mainnet -> Testnet
    "59": "249",  # Agent Arena subnet
}

# Mapping of network names to their chain endpoints
NETWORK_ENDPOINTS = {
    "test": "wss://test.finney.opentensor.ai:443",
    "main": "wss://entrypoint-finney.opentensor.ai:443",
}

# Default subnet IDs for each network
DEFAULT_NETUIDS = {
    "test": 249,
    "main": 59,
}


def get_netuid(network: str = None) -> int:
    """Get the subnet ID from environment variables or defaults.

    Args:
        network: Network name (test/main). If None, uses NETWORK env var.

    Returns:
        int: The subnet ID to use
    """
    if network is None:
        network = os.environ.get("NETWORK", "test")

    # First try to get from environment variable
    netuid = os.environ.get("NETUID")
    if netuid is not None:
        return int(netuid)

    # Otherwise use default based on network
    return DEFAULT_NETUIDS.get(network, 249)  # Default to testnet if network unknown


def get_testnet_netuid(mainnet_netuid: str) -> str:
    """Get the testnet subnet ID for a given mainnet subnet ID."""
    return SUBNET_MAPPINGS.get(str(mainnet_netuid))


def get_mainnet_netuid(testnet_netuid: str) -> str:
    """Get the mainnet subnet ID for a given testnet subnet ID."""
    for mainnet, testnet in SUBNET_MAPPINGS.items():
        if testnet == str(testnet_netuid):
            return mainnet
    return None


def get_chain_endpoint(network: str) -> str:
    """Get the chain endpoint for a given network."""
    return NETWORK_ENDPOINTS.get(network)

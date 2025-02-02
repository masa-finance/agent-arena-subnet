import os
import logging
from startup import WalletManager, ProcessManager
import bittensor as bt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_status_report(
    role,
    uid,
    hotkey,
    registered,
    network,
    netuid,
    axon_port,
    metrics_port,
    grafana_port,
):
    """Print a formatted status report."""
    icon = "🔍" if role == "validator" else "⛏️ "
    role_title = role.capitalize()

    print(f"\n=== {icon} {role_title} Status Report ===\n")
    print("-" * 50)
    print(
        f"""
• {role_title} {uid}
  ├─ Network: {network}
  ├─ Subnet: {netuid}
  ├─ {'✅ Running' if uid else '❌ Not Running'}
  ├─ {'✅ Registered' if registered else '❌ Not Registered'}
  ├─ Axon Port: {axon_port}
  ├─ Metrics Port: {metrics_port}
  └─ Grafana Port: {grafana_port}
  └─ Hotkey: {hotkey}

Starting Masa {role} process...
"""
    )


def main():
    """Main entry point."""
    try:
        # Get environment variables
        role = os.getenv("ROLE", "validator").lower()
        network = os.getenv("SUBTENSOR_NETWORK", "test").lower()
        netuid = int(os.getenv("NETUID"))

        # Get correct ports based on role
        if role == "validator":
            published_axon_port = int(os.getenv("VALIDATOR_AXON_PORT"))
            published_metrics_port = int(os.getenv("VALIDATOR_METRICS_PORT"))
            published_grafana_port = int(os.getenv("VALIDATOR_GRAFANA_PORT"))
        else:
            published_axon_port = int(os.getenv("MINER_AXON_PORT"))
            published_metrics_port = int(os.getenv("MINER_METRICS_PORT"))
            published_grafana_port = int(os.getenv("MINER_GRAFANA_PORT"))

        # Initialize managers
        wallet_manager = WalletManager(role=role, network=network, netuid=netuid)
        process_manager = ProcessManager()

        # Load wallet - this also checks registration
        wallet = wallet_manager.load_wallet()

        # Get UID from subtensor
        subtensor = bt.subtensor(network="test" if network == "test" else None)
        uid = subtensor.get_uid_for_hotkey_on_subnet(
            hotkey_ss58=wallet.hotkey.ss58_address,
            netuid=netuid,
        )

        # Print status before starting
        print_status_report(
            role=role,
            uid=uid,
            hotkey=wallet_manager.hotkey_name,
            registered=True,
            network=network,
            netuid=netuid,
            axon_port=published_axon_port,
            metrics_port=published_metrics_port,
            grafana_port=published_grafana_port,
        )

        # Calculate wallet and hotkey names
        wallet_name = f"subnet_{netuid}"
        hotkey_name = f"{role}_{os.environ.get('REPLICA_NUM', '1')}"

        # Set environment variables for the miner/validator process
        os.environ["AXON_PORT"] = str(published_axon_port)
        os.environ["WALLET_NAME"] = wallet_name
        os.environ["HOTKEY_NAME"] = hotkey_name

        # Build and execute command
        if role == "validator":
            command = process_manager.build_validator_command(
                netuid=netuid,
                network=network,
                wallet_name=wallet_name,
                wallet_hotkey=hotkey_name,
                logging_dir="/root/.bittensor/logs",
                axon_port=published_axon_port,
                prometheus_port=published_metrics_port,
                grafana_port=published_grafana_port,
            )
            process_manager.execute_validator(command)
        else:
            command = process_manager.build_miner_command(
                wallet_name=wallet_name,
                wallet_hotkey=hotkey_name,
                netuid=netuid,
                network=network,
                logging_dir="/root/.bittensor/logs",
                axon_port=published_axon_port,
                prometheus_port=published_metrics_port,
                grafana_port=published_grafana_port,
            )
            process_manager.execute_miner(command)

    except Exception as e:
        logger.error(f"Failed to start {role}: {str(e)}")
        raise


if __name__ == "__main__":
    main()

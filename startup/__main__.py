import os
import logging
from startup.wallet_manager import WalletManager
from startup.process_manager import ProcessManager
from startup.config import get_netuid
import bittensor as bt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_status_report(role, uid, hotkey, registered, network, netuid, port):
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
  ├─ Status: {'✅ Running' if uid else '❌ Not Running'}
  ├─ Registration: {'✅ Registered' if registered else '❌ Not Registered'}
  ├─ Port: {port}
  └─ Hotkey: {hotkey or 'Unknown'}

Starting {role} process...
"""
    )


def main():
    """Main entry point."""
    try:
        # Get environment variables
        role = os.getenv("ROLE", "validator").lower()
        network = os.getenv("SUBTENSOR_NETWORK", "test").lower()
        netuid = get_netuid(network)

        # Get correct ports based on role
        if role == "validator":
            published_axon_port = int(os.getenv("VALIDATOR_AXON_PORT", "8092"))
            published_metrics_port = int(os.getenv("VALIDATOR_METRICS_PORT", "9000"))
            published_grafana_port = int(os.getenv("VALIDATOR_GRAFANA_PORT", "3100"))
        else:
            published_axon_port = int(os.getenv("MINER_AXON_PORT", "8192"))
            published_metrics_port = int(os.getenv("MINER_METRICS_PORT", "9100"))
            published_grafana_port = int(os.getenv("MINER_GRAFANA_PORT", "3000"))

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
            registered=True,  # We know it's registered since we got the UID
            network=network,
            netuid=netuid,
            port=published_axon_port,
            grafana_port=published_grafana_port,
        )

        # Set environment variables for the miner/validator process
        os.environ["AXON_PORT"] = str(published_axon_port)

        # Build and execute command
        if role == "validator":
            command = process_manager.build_validator_command(
                netuid=netuid,
                network=network,
                wallet_name=wallet.name,
                wallet_hotkey=wallet_manager.hotkey_name,
                logging_dir="logs/validator",
                axon_port=published_axon_port,
                prometheus_port=published_metrics_port,
                grafana_port=published_grafana_port,
            )
            process_manager.execute_validator(command)
        else:
            command = process_manager.build_miner_command(
                wallet_name=wallet.name,
                wallet_hotkey=wallet_manager.hotkey_name,
                netuid=netuid,
                network=network,
                logging_dir="logs/miner",
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

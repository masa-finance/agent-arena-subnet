import os
import logging
from typing import List


class ProcessManager:
    """Manages the execution of validator and miner processes."""

    def __init__(self):
        """Initialize the process manager."""
        self.logger = logging.getLogger(__name__)

    def prepare_directories(self):
        """Prepare necessary directories for process execution."""
        state_path = os.path.expanduser("./.bittensor/states")
        os.makedirs(state_path, mode=0o700, exist_ok=True)
        return state_path

    def build_validator_command(
        self,
        netuid: int,
        network: str,
        wallet_name: str,
        wallet_hotkey: str,
        axon_port: int,
        prometheus_port: int,
        grafana_port: int,
    ) -> List[str]:
        """Build the validator command with all necessary arguments."""
        wallet_path = os.path.expanduser("./.bittensor/wallets/")
        state_path = self.prepare_directories()

        command = [
            "python",
            "neurons/validator.py",
            f"--netuid={netuid}",
            f"--wallet.name={wallet_name}",
            f"--wallet.hotkey={wallet_hotkey}",
            f"--wallet.path={wallet_path}",
            f"--logging.logging_dir={state_path}",
            f"--axon.port={axon_port}",
            f"--prometheus.port={prometheus_port}",
            f"--grafana.port={grafana_port}",
            "--logging.debug",
        ]

        if network == "test":
            command.extend(["--subtensor.network=test"])

        return command

    def build_miner_command(
        self,
        wallet_name: str,
        wallet_hotkey: str,
        netuid: int,
        network: str,
        logging_dir: str,
        axon_port: int,
        prometheus_port: int,
        grafana_port: int,
    ) -> List[str]:
        """Build the miner command with all necessary arguments.

        Args:
            wallet_name: Name of the wallet to use
            wallet_hotkey: Name of the hotkey to use
            netuid: Network UID to connect to
            network: Network to connect to (test/main)
            logging_dir: Directory to store logs
            axon_port: Port for the axon server
            prometheus_port: Port for prometheus metrics
            grafana_port: Port for grafana
        Returns:
            Complete command as a list of arguments
        """
        command = [
            "python3",
            "-m",
            "neurons.miner",
            f"--netuid={netuid}",
            f"--wallet.name={wallet_name}",
            f"--wallet.hotkey={wallet_hotkey}",
            f"--logging.directory={logging_dir}",
            f"--axon.port={axon_port}",
            f"--prometheus.port={prometheus_port}",
            f"--grafana.port={grafana_port}",
        ]

        if network == "test":
            command.append("--subtensor.network=test")

        return command

    def execute_validator(self, command: List[str]):
        """Execute the validator process.

        Args:
            command: Complete command as a list of arguments
        """
        self.logger.info(f"Executing validator command: {' '.join(command)}")
        # Use execvp to replace the current process
        os.execvp(command[0], command)

    def execute_miner(self, command: List[str]):
        """Execute the miner process.

        Args:
            command: Complete command as a list of arguments
        """
        self.logger.info(f"Executing miner command: {' '.join(command)}")
        # Use execvp to replace the current process
        os.execvp(command[0], command)

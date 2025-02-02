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
        base_dir = "/root/.bittensor"
        os.makedirs(os.path.join(base_dir, "logs"), mode=0o700, exist_ok=True)
        os.makedirs(os.path.join(base_dir, "wallets"), mode=0o700, exist_ok=True)
        return base_dir

    def build_validator_command(
        self,
        netuid: int,
        network: str,
        wallet_name: str,
        wallet_hotkey: str,
        logging_dir: str,
        axon_port: int,
        prometheus_port: int,
        grafana_port: int,
    ) -> List[str]:
        """Build the validator command with all necessary arguments."""
        base_dir = self.prepare_directories()
        wallet_path = os.path.join(base_dir, "wallets")

        command = [
            "python3",
            "scripts/run_validator.py",
            f"--netuid={netuid}",
            f"--wallet.name={wallet_name}",
            f"--wallet.hotkey={wallet_hotkey}",
            f"--wallet.path={wallet_path}",
            f"--logging.directory={os.path.join(base_dir, 'logs')}",
            f"--logging.logging_dir={os.path.join(base_dir, 'logs')}",
            f"--axon.port={axon_port}",
            f"--prometheus.port={prometheus_port}",
            f"--grafana.port={grafana_port}",
            "--logging.debug",
        ]

        if network == "test":
            command.append("--subtensor.network=test")

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
        """Build the miner command with all necessary arguments."""
        base_dir = self.prepare_directories()
        wallet_path = os.path.join(base_dir, "wallets")

        command = [
            "python3",
            "scripts/run_miner.py",
            f"--netuid={netuid}",
            f"--wallet.name={wallet_name}",
            f"--wallet.hotkey={wallet_hotkey}",
            f"--wallet.path={wallet_path}",
            f"--logging.directory={os.path.join(base_dir, 'logs')}",
            f"--logging.logging_dir={os.path.join(base_dir, 'logs')}",
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

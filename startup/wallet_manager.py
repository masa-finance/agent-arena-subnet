import os
import logging
import bittensor as bt
from contextlib import redirect_stdout
from startup.config import get_chain_endpoint, get_netuid

logger = logging.getLogger(__name__)


class WalletManager:
    """Manages wallet operations for validators and miners."""

    def __init__(self, role: str, network: str, netuid: int):
        """Initialize the wallet manager.

        Args:
            role: Role of the node (validator/miner)
            network: Network to connect to (test/main)
            netuid: Network UID to register on
        """
        self.role = role
        self.network = network
        self.netuid = netuid
        self.logger = logging.getLogger(__name__)

        # Initialize wallet
        self.wallet = self.load_wallet()

    def load_wallet(self) -> bt.wallet:
        """Load or create wallet based on environment variables.

        Returns:
            Loaded wallet
        """
        # Configure network endpoint
        chain_endpoint = get_chain_endpoint(self.network)
        bt.subtensor.set_network_endpoint(chain_endpoint)

        # Get wallet name from env or use default
        wallet_name = os.getenv("BT_WALLET_NAME", "default")
        self.logger.info(f"Using wallet: {wallet_name}")

        # Load or create wallet
        wallet = bt.wallet(name=wallet_name)

        # Ensure keys exist
        if not wallet.coldkeypub_file.exists_on_device():
            self.logger.error("No coldkey found. Please create a wallet first.")
            raise Exception("No coldkey found")

        if not wallet.hotkey_file.exists_on_device():
            self.logger.error("No hotkey found. Please create a wallet first.")
            raise Exception("No hotkey found")

        # Log wallet info
        self.logger.info(f"Loaded wallet: {wallet}")
        self.logger.info(f"Coldkey: {wallet.coldkeypub.ss58_address}")
        self.logger.info(f"Hotkey: {wallet.hotkey.ss58_address}")

        return wallet

    def get_wallet(self) -> bt.wallet:
        """Get the loaded wallet.

        Returns:
            Loaded wallet
        """
        return self.wallet

    def setup_wallet_directories(self):
        """Create wallet directories with proper permissions."""
        wallet_dir = os.path.expanduser(f"~/.bittensor/wallets/{self.wallet.name}")
        os.makedirs(wallet_dir, mode=0o700, exist_ok=True)
        os.makedirs(os.path.join(wallet_dir, "hotkeys"), mode=0o700, exist_ok=True)

    def initialize_wallet(
        self, coldkey_mnemonic: str = None, is_validator: bool = False
    ):
        """Initialize wallet with coldkey and hotkey.

        Args:
            coldkey_mnemonic: Optional mnemonic for coldkey regeneration
            is_validator: Whether this is a validator wallet

        Returns:
            bt.wallet: Initialized wallet object
        """
        wallet = bt.wallet(
            name=self.wallet.name,
            hotkey=self.wallet.hotkey,
            path=os.path.expanduser("~/.bittensor/wallets/"),
        )

        # Handle coldkey
        coldkey_path = os.path.join(wallet.path, self.wallet.name, "coldkey")
        if not os.path.exists(coldkey_path):
            if is_validator and not coldkey_mnemonic:
                raise Exception(
                    "No coldkey found and COLDKEY_MNEMONIC not provided for validator"
                )
            if coldkey_mnemonic:
                self._regenerate_coldkey(wallet, coldkey_mnemonic)

        # Handle hotkey
        hotkey_path = os.path.join(
            wallet.path, self.wallet.name, "hotkeys", self.wallet.hotkey
        )
        if not os.path.exists(hotkey_path):
            self._create_hotkey(wallet)

        return wallet

    def _regenerate_coldkey(self, wallet, mnemonic):
        """Regenerate coldkey from mnemonic."""
        self.logger.info("Regenerating coldkey from mnemonic")
        with open(os.devnull, "w") as devnull:
            with redirect_stdout(devnull):
                try:
                    wallet.regenerate_coldkey(
                        mnemonic=mnemonic,
                        use_password=False,
                        overwrite=False,
                    )
                except Exception as e:
                    if "already exists" in str(e):
                        self.logger.info(
                            "Coldkey already exists, skipping regeneration"
                        )
                    else:
                        raise

    def _create_hotkey(self, wallet):
        """Create new hotkey."""
        self.logger.info(f"Creating new hotkey {self.wallet.hotkey}")
        with open(os.devnull, "w") as devnull:
            with redirect_stdout(devnull):
                try:
                    wallet.create_new_hotkey(
                        use_password=False,
                        overwrite=False,
                    )
                except Exception as e:
                    if "already exists" in str(e):
                        self.logger.info("Hotkey already exists, skipping creation")
                    else:
                        raise

    def update_hotkey_mappings(self, wallet, uid: int, role: str):
        """Update hotkey mappings file with current hotkey info.

        Args:
            wallet: Initialized wallet object
            uid: UID assigned to the hotkey
            role: Role of the node (validator/miner)
        """
        mappings_file = os.path.expanduser("~/.bt-masa/hotkey_mappings.json")
        os.makedirs(os.path.dirname(mappings_file), mode=0o700, exist_ok=True)

        mappings = {}
        if os.path.exists(mappings_file):
            try:
                with open(mappings_file, "r") as f:
                    mappings = json.load(f)
            except json.JSONDecodeError:
                self.logger.warning(
                    "Could not parse existing mappings file, starting fresh"
                )

        mappings[wallet.hotkey.ss58_address] = {
            "uid": uid,
            "role": role,
            "netuid": self.netuid,
            "wallet_name": self.wallet.name,
            "hotkey_name": self.wallet.hotkey,
        }

        with open(mappings_file, "w") as f:
            json.dump(mappings, f, indent=2)
        self.logger.info("Updated hotkey mappings in %s", mappings_file)

import logging
import os
import json
import bittensor as bt
import time
from substrateinterface.exceptions import SubstrateRequestException

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
        self.subtensor = None

        # Get replica number from env
        self.replica_num = os.environ.get("REPLICA_NUM", "1")

        # Set wallet name based on subnet and hotkey based on role/replica
        self.wallet_name = f"subnet_{netuid}"
        self.hotkey_name = f"{role}_{self.replica_num}"

        # Set validator-specific environment variables if this is a validator
        if role == "validator":
            os.environ["VALIDATOR_WALLET_NAME"] = self.wallet_name
            os.environ["VALIDATOR_HOTKEY_NAME"] = self.hotkey_name

        # Initialize wallet
        self.wallet = self.load_wallet()

    def load_wallet(self) -> bt.wallet:
        """Load or create wallet based on environment variables.

        Returns:
            Loaded wallet
        """
        # Initialize subtensor - only specify network if it's test
        self.subtensor = (
            bt.subtensor(network="test") if self.network == "test" else bt.subtensor()
        )

        print("=== Wallet Setup ===")
        print(f"Using wallet: {self.wallet_name}")
        self.logger.info("Using wallet: %s", self.wallet_name)

        # First just load/create wallet without hotkey
        self.wallet = bt.wallet(name=self.wallet_name)

        # Check for coldkey and regenerate if needed
        coldkey_path = os.path.join(
            "/root/.bittensor/wallets", self.wallet_name, "coldkey"
        )
        if os.path.exists(coldkey_path):
            print(f"Found existing coldkey at {coldkey_path}")
            self.logger.info("Found existing coldkey at %s", coldkey_path)
        else:
            print(f"No coldkey found at {coldkey_path}")
            self.logger.info("No coldkey found at %s", coldkey_path)
            mnemonic = os.environ.get("COLDKEY_MNEMONIC")
            if not mnemonic:
                print("ERROR: COLDKEY_MNEMONIC environment variable is required")
                self.logger.error("COLDKEY_MNEMONIC environment variable is required")
                raise Exception("COLDKEY_MNEMONIC not provided")

            print("Attempting to regenerate coldkey from mnemonic...")
            self.logger.info("Attempting to regenerate coldkey from mnemonic")
            try:
                self.wallet.regenerate_coldkey(
                    mnemonic=mnemonic, use_password=False, overwrite=True
                )
                print("Successfully regenerated coldkey")
                self.logger.info("Successfully regenerated coldkey")
            except Exception as e:
                print(f"Failed to regenerate coldkey: {str(e)}")
                self.logger.error("Failed to regenerate coldkey: %s", str(e))
                raise

        # Now that we have a coldkey, set up the hotkey
        self.setup_hotkey()

        # Check registration status
        is_registered = self.subtensor.is_hotkey_registered(
            netuid=self.netuid,
            hotkey_ss58=self.wallet.hotkey.ss58_address,
        )

        if not is_registered:
            print(
                f"Hotkey {self.hotkey_name} is not registered, attempting registration..."
            )
            self.logger.info(
                "Hotkey %s is not registered, attempting registration...",
                self.hotkey_name,
            )
            uid = self.register()
            if uid is not None:
                print(
                    f"Successfully registered hotkey {self.hotkey_name} with UID {uid}"
                )
                self.logger.info(
                    "Successfully registered hotkey %s with UID %d",
                    self.hotkey_name,
                    uid,
                )
            else:
                print(f"Failed to register hotkey {self.hotkey_name}")
                self.logger.error("Failed to register hotkey %s", self.hotkey_name)
                raise Exception("Failed to register hotkey")
        else:
            uid = self.subtensor.get_uid_for_hotkey_on_subnet(
                hotkey_ss58=self.wallet.hotkey.ss58_address,
                netuid=self.netuid,
            )
            print(f"Hotkey {self.hotkey_name} is already registered with UID {uid}")
            self.logger.info(
                "Hotkey %s is already registered with UID %d", self.hotkey_name, uid
            )
            self.update_hotkey_mappings(uid)

        return self.wallet

    def get_wallet(self) -> bt.wallet:
        """Get the loaded wallet.

        Returns:
            Loaded wallet
        """
        return self.wallet

    def setup_hotkey(self):
        """Set up hotkey after coldkey is established."""
        self.logger.info("Setting up hotkey %s", self.hotkey_name)

        # First create the wallet with the hotkey name we want and explicit path
        self.wallet = bt.wallet(
            name=self.wallet_name,
            hotkey=self.hotkey_name,
            path="/root/.bittensor/wallets/",
        )

        hotkey_path = os.path.join(
            "/root/.bittensor/wallets", self.wallet_name, "hotkeys", self.hotkey_name
        )
        if not os.path.exists(hotkey_path):
            self.logger.info("Creating new hotkey %s", self.hotkey_name)
            self.wallet.create_new_hotkey(use_password=False, overwrite=False)
        else:
            self.logger.info("Found existing hotkey %s", self.hotkey_name)

    def update_hotkey_mappings(self, uid: int):
        """Update hotkey mappings file with current hotkey info.

        Args:
            uid: UID assigned to the hotkey
        """
        mappings_file = os.path.expanduser("./.bt-masa/hotkey_mappings.json")
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

        mappings[self.wallet.hotkey.ss58_address] = {
            "uid": uid,
            "role": self.role,
            "netuid": self.netuid,
            "wallet_name": self.wallet.name,
            "hotkey_name": self.hotkey_name,
        }

    def register(self):
        """Register wallet with subnet."""
        self.logger.info("Starting registration for hotkey %s", self.hotkey_name)

        while True:
            try:
                # Attempt registration
                success = self.subtensor.burned_register(
                    wallet=self.wallet,
                    netuid=self.netuid,
                )

                if success:
                    # Get the UID after successful registration
                    uid = self.subtensor.get_uid_for_hotkey_on_subnet(
                        hotkey_ss58=self.wallet.hotkey.ss58_address,
                        netuid=self.netuid,
                    )
                    self.update_hotkey_mappings(uid)
                    print("\n=== REGISTRATION SUCCESSFUL ===")
                    print(f"Hotkey: {self.hotkey_name}")
                    print(f"UID: {uid}")
                    print(f"Network: {self.network}")
                    print(f"Netuid: {self.netuid}")
                    print("===============================\n")
                    return uid

                self.logger.warning(
                    "Registration attempt failed, retrying in 10 seconds..."
                )
                time.sleep(10)

            except SubstrateRequestException as e:
                error_msg = str(e)
                if "Priority is too low" in error_msg:
                    self.logger.warning(
                        "Registration queued, retrying in 10 seconds... (Priority is too low)"
                    )
                    time.sleep(10)
                elif "Invalid Transaction" in error_msg:
                    self.logger.warning(
                        "Registration blocked, retrying in 10 seconds... (Invalid Transaction)"
                    )
                    time.sleep(10)
                else:
                    self.logger.error(
                        "Unexpected registration error, retrying in 10 seconds..."
                    )
                    time.sleep(10)
            except Exception:
                self.logger.warning("Registration failed, retrying in 10 seconds...")

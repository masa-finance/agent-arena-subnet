import os
import logging
import bittensor as bt
from contextlib import redirect_stdout
import json
import time

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

        print(f"\n=== Wallet Setup ===")
        print(f"Using wallet: {self.wallet_name}")
        self.logger.info(f"Using wallet: {self.wallet_name}")

        # First just load/create wallet without hotkey
        self.wallet = bt.wallet(name=self.wallet_name)

        # Check for coldkey and regenerate if needed
        coldkey_path = os.path.join(
            "/root/.bittensor/wallets", self.wallet_name, "coldkey"
        )
        if os.path.exists(coldkey_path):
            print(f"Found existing coldkey at {coldkey_path}")
            self.logger.info(f"Found existing coldkey at {coldkey_path}")
        else:
            print(f"No coldkey found at {coldkey_path}")
            self.logger.info(f"No coldkey found at {coldkey_path}")
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
                self.logger.error(f"Failed to regenerate coldkey: {str(e)}")
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
                f"Hotkey {self.hotkey_name} is not registered, attempting registration..."
            )
            uid = self.register()
            if uid is not None:
                print(
                    f"Successfully registered hotkey {self.hotkey_name} with UID {uid}"
                )
                self.logger.info(
                    f"Successfully registered hotkey {self.hotkey_name} with UID {uid}"
                )
            else:
                print(f"Failed to register hotkey {self.hotkey_name}")
                self.logger.error(f"Failed to register hotkey {self.hotkey_name}")
                raise Exception("Failed to register hotkey")
        else:
            uid = self.subtensor.get_uid_for_hotkey_on_subnet(
                hotkey_ss58=self.wallet.hotkey.ss58_address,
                netuid=self.netuid,
            )
            print(f"Hotkey {self.hotkey_name} is already registered with UID {uid}")
            self.logger.info(
                f"Hotkey {self.hotkey_name} is already registered with UID {uid}"
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
        self.logger.info(f"Setting up hotkey {self.hotkey_name}")

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
            self.logger.info(f"Creating new hotkey {self.hotkey_name}")
            self.wallet.create_new_hotkey(use_password=False, overwrite=False)
        else:
            self.logger.info(f"Found existing hotkey {self.hotkey_name}")

    def update_hotkey_mappings(self, uid: int):
        """Update hotkey mappings file with current hotkey info.

        Args:
            uid: UID assigned to the hotkey
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

        mappings[self.wallet.hotkey.ss58_address] = {
            "uid": uid,
            "role": self.role,
            "netuid": self.netuid,
            "wallet_name": self.wallet.name,
            "hotkey_name": self.hotkey_name,
        }

        with open(mappings_file, "w") as f:
            json.dump(mappings, f, indent=2)
        self.logger.info("Updated hotkey mappings in %s", mappings_file)

    def register(self):
        """Register wallet with subnet, retrying indefinitely on failure."""
        while True:
            try:
                # For miners, use pow registration
                self.logger.info("Starting POW registration for miner hotkey...")
                success = self.subtensor.pow_register_extrinsic(
                    wallet=self.wallet,
                    netuid=self.netuid,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )

                if success:
                    # Check registration and get UID
                    is_registered = self.subtensor.is_hotkey_registered(
                        netuid=self.netuid,
                        hotkey_ss58=self.wallet.hotkey.ss58_address,
                    )
                    if is_registered:
                        uid = self.subtensor.get_uid_for_hotkey_on_subnet(
                            hotkey_ss58=self.wallet.hotkey.ss58_address,
                            netuid=self.netuid,
                        )
                        self.logger.info(f"Registration successful - UID: {uid}")
                        self.update_hotkey_mappings(uid)
                        return uid
                    else:
                        self.logger.warning(
                            "Registration appeared to succeed but hotkey is not registered"
                        )
                else:
                    self.logger.warning("Registration failed")
            except Exception as e:
                self.logger.warning(f"Registration failed: {str(e)}")
                time.sleep(10)

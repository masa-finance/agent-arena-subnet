import logging
import bittensor as bt
from startup.wallet_manager import WalletManager

logger = logging.getLogger(__name__)


class RegistrationManager:
    """Manages registration of nodes on the network."""

    def __init__(self, wallet_manager: WalletManager):
        """Initialize the registration manager."""
        self.wallet_manager = wallet_manager
        self.logger = logging.getLogger(__name__)
        self.uid = None
        self.hotkey_ss58 = None
        self.is_registered = False

    def check_registration(self, wallet: bt.wallet, netuid: int) -> tuple[bool, int]:
        """Check if a wallet is registered on the network.

        Args:
            wallet: Wallet to check registration for
            netuid: Network UID to check registration on

        Returns:
            Tuple of (is_registered, uid)
        """
        subtensor = bt.subtensor()
        is_registered = subtensor.is_hotkey_registered(
            netuid=netuid,
            hotkey_ss58=wallet.hotkey.ss58_address,
        )
        uid = None

        if is_registered:
            uid = subtensor.get_uid_for_hotkey_on_subnet(
                hotkey_ss58=wallet.hotkey.ss58_address,
                netuid=netuid,
            )
            self.logger.info(f"Hotkey is registered with UID {uid}")
            self.uid = uid
            self.hotkey_ss58 = wallet.hotkey.ss58_address
            self.is_registered = True

        return is_registered, uid

    def register_if_needed(
        self, wallet: bt.wallet, netuid: int, is_validator: bool = False
    ) -> tuple[bool, int]:
        """Register a wallet if it's not already registered.

        Args:
            wallet: Wallet to register
            netuid: Network UID to register on
            is_validator: Whether this is a validator registration

        Returns:
            Tuple of (success, uid)
        """
        # Ensure hotkey is set up before checking registration
        self.wallet_manager.setup_hotkey()

        is_registered, uid = self.check_registration(wallet, netuid)

        if is_registered:
            self.logger.info("Already registered with UID %s", uid)
            self.wallet_manager.update_hotkey_mappings(uid)
            return True, uid

        if is_validator:
            # For validators, use burned registration
            self.logger.info(
                "Starting burned registration process for validator hotkey"
            )

            # Check current balance
            subtensor = bt.subtensor()
            balance = subtensor.get_balance(wallet.coldkeypub.ss58_address)
            self.logger.info(f"Current balance: {balance} TAO")

            # Get registration cost
            cost = subtensor.recycle(netuid)
            self.logger.info(f"Registration cost: {cost} TAO")

            if balance < cost:
                raise Exception(
                    f"Insufficient balance ({balance} TAO) for registration. Need {cost} TAO"
                )

            self.logger.info("Balance sufficient for registration, proceeding...")
            self.logger.info(
                f"This process will burn {cost} TAO from your balance of {balance} TAO"
            )
            self.logger.info("Starting registration (this may take a few minutes)")

            # First check if registration is still needed
            is_registered, uid = self.check_registration(wallet, netuid)
            if is_registered:
                self.logger.info("Already registered with UID %s", uid)
                return True, uid

            success = subtensor.burned_register(
                wallet=wallet,
                netuid=netuid,
            )

            if success:
                self.logger.info("Registration successful")
                is_registered, uid = self.check_registration(wallet, netuid)
                if is_registered:
                    self.wallet_manager.update_hotkey_mappings(uid)
                return is_registered, uid
            else:
                raise Exception("Registration failed")
        else:
            # For miners, use pow registration
            self.logger.info("Starting POW registration for miner hotkey")
            success = subtensor.register(
                wallet=wallet,
                netuid=netuid,
            )

            if success:
                self.logger.info("Registration successful")
                is_registered, uid = self.check_registration(wallet, netuid)
                if is_registered:
                    self.wallet_manager.update_hotkey_mappings(uid)
                return is_registered, uid
            else:
                raise Exception("Registration failed")

    def verify_registration_status(self, wallet: bt.wallet, netuid: int):
        """Verify registration status and log details.

        Args:
            wallet: Wallet to verify
            netuid: Network UID to check
        """
        self.logger.info("Double checking registration status:")
        self.logger.info(f"Checking netuid {netuid}")
        self.logger.info(f"Hotkey address: {wallet.hotkey.ss58_address}")

        subtensor = bt.subtensor()

        # Check registration on any subnet
        any_subnet = subtensor.is_hotkey_registered_any(wallet.hotkey.ss58_address)
        self.logger.info(f"Is registered on any subnet: {any_subnet}")

        # Check specific subnet registration again
        subnet_check = subtensor.is_hotkey_registered_on_subnet(
            wallet.hotkey.ss58_address, netuid
        )
        self.logger.info(f"Is registered on subnet {netuid}: {subnet_check}")

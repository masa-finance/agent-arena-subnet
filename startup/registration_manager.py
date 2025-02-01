import logging
import bittensor as bt
import time


class RegistrationManager:
    """Manages registration operations for validators and miners."""

    def __init__(self, subtensor: bt.subtensor):
        """Initialize the registration manager.

        Args:
            subtensor: Initialized subtensor connection
        """
        self.subtensor = subtensor
        self.logger = logging.getLogger(__name__)

    def check_registration(self, wallet: bt.wallet, netuid: int) -> tuple[bool, int]:
        """Check if a wallet's hotkey is registered.

        Args:
            wallet: The wallet to check
            netuid: Network UID to check registration on

        Returns:
            tuple: (is_registered, uid if registered else None)
        """
        is_registered = self.subtensor.is_hotkey_registered(
            netuid=netuid,
            hotkey_ss58=wallet.hotkey.ss58_address,
        )

        if is_registered:
            uid = self.subtensor.get_uid_for_hotkey_on_subnet(
                hotkey_ss58=wallet.hotkey.ss58_address,
                netuid=netuid,
            )
            self.logger.info(f"Hotkey is registered with UID {uid}")
            return True, uid

        self.logger.info("Hotkey is not registered")
        return False, None

    def register_if_needed(
        self, wallet: bt.wallet, netuid: int, is_validator: bool = False
    ) -> tuple[bool, int]:
        """Register the wallet if not already registered.

        Args:
            wallet: The wallet to register
            netuid: Network UID to register on
            is_validator: Whether this is a validator registration

        Returns:
            tuple: (success, uid if successful else None)
        """
        # First check current registration status
        is_registered, uid = self.check_registration(wallet, netuid)
        if is_registered:
            return True, uid

        # Debug info
        self.logger.info(f"Bittensor version: {bt.__version__}")
        self.logger.info(f"Available subtensor methods: {dir(self.subtensor)}")

        # Perform registration with retries
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                success = self.subtensor.burned_register_extrinsic(
                    wallet=wallet,
                    netuid=netuid,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )

                if success:
                    break
                else:
                    retry_count += 1
                    self.logger.warning(
                        f"Registration attempt {retry_count} failed, retrying in 10 seconds..."
                    )
                    time.sleep(10)

            except Exception as e:
                error_str = str(e)
                if "Priority is too low" in error_str:
                    retry_count += 1
                    self.logger.warning(
                        f"Got priority error on attempt {retry_count}, retrying in 10 seconds..."
                    )
                    time.sleep(10)
                else:
                    role = "validator" if is_validator else "miner"
                    raise Exception(f"Failed to register {role} hotkey - {str(e)}")

        if retry_count >= max_retries:
            role = "validator" if is_validator else "miner"
            raise Exception(
                f"Failed to register {role} hotkey after {max_retries} attempts"
            )

        # Verify registration and get UID
        is_registered, uid = self.check_registration(wallet, netuid)
        if is_registered:
            new_balance = self.subtensor.get_balance(wallet.coldkeypub.ss58_address)
            self.logger.info(f"Successfully registered hotkey with UID {uid}")
            self.logger.info(
                f"New balance after registration: {new_balance} TAO (burned {balance - new_balance} TAO)"
            )
            return True, uid
        else:
            raise Exception(
                "Registration appeared to succeed but hotkey is not registered"
            )

    def verify_registration_status(self, wallet: bt.wallet, netuid: int):
        """Perform detailed registration status verification.

        Args:
            wallet: The wallet to verify
            netuid: Network UID to check
        """
        self.logger.info("Double checking registration status:")
        self.logger.info(f"Checking netuid {netuid}")
        self.logger.info(f"Hotkey address: {wallet.hotkey.ss58_address}")

        # Check registration on any subnet
        any_subnet = self.subtensor.is_hotkey_registered_any(wallet.hotkey.ss58_address)
        self.logger.info(f"Is registered on any subnet: {any_subnet}")

        # Check specific subnet registration
        subnet_check = self.subtensor.is_hotkey_registered_on_subnet(
            wallet.hotkey.ss58_address, netuid
        )
        self.logger.info(f"Is registered on subnet {netuid}: {subnet_check}")

        return subnet_check

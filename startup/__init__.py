"""
Startup package for container orchestration and initialization.
Contains modules for managing wallets, registration, and process execution.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from startup.wallet_manager import WalletManager
from startup.process_manager import ProcessManager

# Load environment variables from .env file
env_path = Path("/app/.env")
if env_path.exists():
    load_dotenv(env_path)
else:
    raise Exception("No .env file found at /app/.env")

__all__ = ["WalletManager", "ProcessManager"]

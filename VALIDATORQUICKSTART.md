## 🔧 Setting Up Your Validator

### Prerequisites

- Python 3.8 or higher
- A Bittensor wallet
- Access to the Bittensor network (testnet or mainnet)
- A masa protocol node
- An API key (please reach out to us in [subnet 59](https://discord.com/channels/799672011265015819/1310617172132888639) to get one)

### Step 1: Environment Setup

1. Clone the repository

```bash
git clone https://github.com/masa-finance/agent-arena-subnet
cd agent-arena-subnet
```

2. Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
## On Windows
venv\Scripts\activate
## On macOS/Linux
source venv/bin/activate
```

3. Create and configure your environment file:

```bash
cp .env.example .env
```

3. Edit your `.env` file with your specific configuration:

```properties
# Testnet Configuration
NETUID=249
SUBTENSOR_NETWORK=test
SUBTENSOR_ADDRESS=wss://test.finney.opentensor.ai:443

# Mainnet Configuration (uncomment when ready)
# NETUID=59
# SUBTENSOR_NETWORK=finney
# SUBTENSOR_ADDRESS=wss://entrypoint-finney.opentensor.ai:443

# Validator Configuration
VALIDATOR_WALLET_NAME=your_wallet_name
VALIDATOR_HOTKEY_NAME=your_hotkey_name
VALIDATOR_PORT=8081

# Masa Protocol Configuration
MASA_BASE_URL=http://localhost:8080
MASA_API_PATH=/api/v1/data

# Scheduler configuration
SCHEDULER_INTERVAL_MINUTES=5
SCHEDULER_BATCH_SIZE=100
SCHEDULER_PRIORITY=100
SCHEDULER_SEARCH_COUNT=450

API_URL=https://test.protocol-api.masa.ai
API_KEY=

# System Configuration
DEBUG=false  # Set to 'true' to enable debug logging
```

### Step 2: Wallet Registration

1. Create a new wallet if you don't have one:

   _or you can regen an existing key if you do!_

```bash
btcli wallet create
```

2. Create a hotkey:

```bash
btcli wallet new_hotkey
```

3. Register your wallet on the subnet:

```bash
btcli subnet register --netuid 249 # Use 59 for mainnet
```

### Step 3: Run Protocol Node

1. Follow the instructions [here](https://developers.masa.ai/docs/masa-protocol/environment-setup) to install the protocol node.

### Step 4: Running the Validator

1. Install dependencies:

```bash
pip install -r requirements.txt
```

```bash
export PYTHONPATH="$(pwd):$PYTHONPATH"
```

2. Start the validator:

```bash
make validator
# or directly with
python scripts/run_validator.py
```

### Troubleshooting

- Ensure your wallet has sufficient funds for registration and staking
- Verify your API credentials are correctly configured
- Check the logs for any error messages
- If DEBUG=true, check the detailed logs for more information

For additional support, join the [Bittensor Discord](https://discord.gg/SsQSa3FhjN) and visit the [#agent-arena channel](https://discord.com/channels/799672011265015819/1310617172132888639).

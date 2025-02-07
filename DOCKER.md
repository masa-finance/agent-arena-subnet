ager:Found existing coldkey at /root/.bittensor/wallets/subnet_249/coldkey
masa-node-1  | INFO:startup.wallet_manager:Setting up hotkey miner_1
masa-node-1  | INFO:startup.wallet_manager:Found existing hotkey miner_1
masa-node-1  | Hotkey miner_1 is already registered with UID 42
masa-node-1  | INFO:startup.wallet_manager:Hotkey miner_1 is already registered with UID 42
masa-node-1  | INFO:__main__:Wallet loaded successfully: 5CRhHhD2Z93paUTs2yAUhbqWdsvMZcTViynAreicZi1XAvMx
masa-node-1  | INFO:__main__:Retrieving UID from subtensor...
masa-node-1  | INFO:__main__:Retrieved UID: 42
masa-node-1  | 
masa-node-1  | === ⛏️  Miner Status Report ===
masa-node-1  | 
masa-node-1  | --------------------------------------------------
masa-node-1  | 
masa-node-1  | • Miner 42
masa-node-1  |   ├─ Network: test
masa-node-1  |   ├─ Subnet: 249
masa-node-1  |   ├─ ✅ Running
masa-node-1  |   ├─ ✅ Registered
masa-node-1  |   ├─ Axon Port: 8242
masa-node-1  |   ├─ Metrics Port: 8101
masa-node-1  |   └─ Grafana Port: 3101
masa-node-1  |   └─ Hotkey: miner_1
masa-node-1  | 
masa-node-1  | Starting Masa miner process...
masa-node-1  | 
masa-node-1  | INFO:__main__:Executing miner command: ['python3', 'scripts/run_miner.py', '--netuid=249', '--wallet.name=subnet_249', '--wallet.hotkey=miner_1', '--wallet.path=/root/.bittensor/wallets', '--logging.directory=/root/.bittensor/logs', '--logging.logging_dir=/root/.bittensor/logs', '--axon.port=8242', '--prometheus.port=8101', '--grafana.port=3101', '--subtensor.network=test']
masa-node-1  | INFO:startup.process_manager:Executing miner command: python3 scripts/run_miner.py --netuid=249 --wallet.name=subnet_249 --wallet.hotkey=miner_1 --wallet.path=/root/.bittensor/wallets --logging.directory=/root/.bittensor/logs --logging.logging_dir=/root/.bittensor/logs --axon.port=8242 --prometheus.port=8101 --grafana.port=3101 --subtensor.network=test
masa-node-1  | 2025-02-07 05:34:00.106 | INFO | chain_utils:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.131 | INFO | post_ip_to_chain:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.131 | INFO | interface:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.232 | INFO | fetch_nodes:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.232 | INFO | metagraph:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.406 | INFO | nonce_management:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.407 | INFO | nonce_management:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.407 | INFO | server:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.408 | INFO | signatures:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.427 | INFO | utils:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.435 | INFO | key_management:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.436 | INFO | dependencies:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.437 | INFO | encryption:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.437 | INFO | handshake:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.457 | INFO | miner:get_logger:56 - Logging mode is INFO
masa-node-1  | 2025-02-07 05:34:00.677 | INFO | chain_utils:load_hotkey_keypair:98 - Loaded keypair from /root/.bittensor/wallets/subnet_249/hotkeys/miner_1
masa-node-1  | 2025-02-07 05:34:00.677 | INFO | interface:_get_chain_endpoint:15 - Using chain address: wss://test.finney.opentensor.ai:443
masa-node-1  | 2025-02-07 05:34:01.452 | INFO | interface:get_substrate:39 - Connected to wss://test.finney.opentensor.ai:443
masa-node-1  | 2025-02-07 05:34:01.453 | INFO | metagraph:load_nodes:85 - Loading nodes from nodes.json
masa-node-1  | 2025-02-07 05:34:01.454 | INFO | metagraph:sync_nodes:64 - Syncing nodes...
masa-node-1  | 2025-02-07 05:34:01.454 | INFO | interface:_get_chain_endpoint:15 - Using chain address: wss://test.finney.opentensor.ai:443
masa-node-1  | 2025-02-07 05:34:02.222 | INFO | interface:get_substrate:39 - Connected to wss://test.finney.opentensor.ai:443
masa-node-1  | Traceback # Docker Deployment for Agent Arena

This guide covers the different ways to run Agent Arena nodes using Docker.

## Prerequisites

- Docker installed
- A coldkey mnemonic
- Enough tTAO or real TAO for registration
- Twitter/X account for your agent

## Key Management

We keep it simple:
- Put your coldkey mnemonic in `.env`
- All keys are stored in `.bittensor/` directory
- Each miner/validator gets its own hotkey automatically
- No manual key management needed

## Deployment Options

### 1. Single Node with Docker Compose
The simplest way to run one node:

```bash
# Clone and configure
git clone https://github.com/masa-finance/agent-arena-subnet.git
cd agent-arena-subnet
cp .env.sample .env
# Edit .env with your settings

# Run a miner
docker-compose up

# Or run a validator
ROLE=validator docker-compose up
```

### 2. Multi-Node with start.sh
For running multiple nodes on one machine:

1. Configure `.env`:
   ```env
   # Required settings
   COLDKEY_MNEMONIC="your mnemonic here"
   
   # Specify instance counts
   VALIDATOR_COUNT=2  # Run 2 validators
   MINER_COUNT=3     # Run 3 miners
   
   # Add verification tweet IDs for miners
   TWEET_VERIFICATION_ID_1="your tweet id"
   TWEET_VERIFICATION_ID_2="your tweet id"
   TWEET_VERIFICATION_ID_3="your tweet id"
   ```

2. Start your nodes:
   ```bash
   ./start.sh
   ```

3. Monitor your nodes:
   ```bash
   # Check logs
   docker logs --tail 50 masa_validator_1
   docker logs --tail 50 masa_miner_1
   
   # Check subnet status
   btcli subnet metagraph --netuid 249 --network test
   ```

## Port Allocation

Each instance gets unique ports:

Validators:
- Axon: 8142, 8143, 8144, ...
- Metrics: 8001, 8002, 8003, ...
- Grafana: 3001, 3002, 3003, ...

Miners:
- Axon: 8242, 8243, 8244, ...
- Metrics: 8101, 8102, 8103, ...
- Grafana: 3101, 3102, 3103, ...

## Cleanup

```bash
# If using Docker Compose
docker-compose down

# If using start.sh
docker ps -a | grep 'masa_' | awk '{print $1}' | xargs -r docker stop
docker ps -a | grep 'masa_' | awk '{print $1}' | xargs -r docker rm
```

## Security Best Practices

- Keep `.env` file secure (never commit it)
- Backup `.bittensor` directory regularly
- Each container uses unique ports
- Keys stored safely in `.bittensor` directory

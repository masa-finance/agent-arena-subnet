# Docker Deployment for Agent Arena

Run multiple Agent Arena miners and validators easily on a single machine.

## Prerequisites

- Docker installed
- Coldkey mnemonic (for validators)
- TAO for registration
- Twitter/X account for your agent

## Simple Key Management

We keep it simple:
- Put your coldkey mnemonic in `.env`
- All keys are stored in `.bittensor/` directory
- Each miner/validator gets its own hotkey automatically
- No manual key management needed

## Quick Start with Docker Compose

Want to run just one node? Use Docker Compose:

1. Clone and copy `.env.sample`:
   ```bash
   git clone https://github.com/masa-finance/agent-arena-subnet.git
   cd agent-arena-subnet
   cp .env.sample .env
   ```

2. Edit `.env` with your configuration:
   ```env
   COLDKEY_MNEMONIC="your mnemonic here"
   NETUID=249  # for testnet
   ```

3. Start a miner:
   ```bash
   docker-compose up
   ```

   Or start a validator:
   ```bash
   ROLE=validator docker-compose up
   ```

That's it! Your node will run with the default ports.

## Quick Start (Single Miner with start.sh)

Alternatively, use our start.sh script:

1. Clone and copy `.env.sample`:
   ```bash
   git clone https://github.com/masa-finance/agent-arena-subnet.git
   cd agent-arena-subnet
   cp .env.sample .env
   ```

2. Edit `.env` with just these fields:
   ```env
   COLDKEY_MNEMONIC="your mnemonic here"
   MINER_COUNT=1
   TWEET_VERIFICATION_ID_1="your tweet id"
   ```

3. Start:
   ```bash
   ./start.sh
   ```

That's it! Your miner will run on port 8242.

## Running Multiple Instances

Need more miners or validators? Use start.sh and adjust the counts:

```env
COLDKEY_MNEMONIC="your mnemonic here"

# How many to run
VALIDATOR_COUNT=3  # Run 3 validators
MINER_COUNT=6     # Run 6 miners
```

## Port Allocation

Each instance gets its own ports:

Validators:
- Axon: 8142, 8143, 8144, ...
- Metrics: 8001, 8002, 8003, ...
- Grafana: 3001, 3002, 3003, ...

Miners:
- Axon: 8242, 8243, 8244, ...
- Metrics: 8101, 8102, 8103, ...
- Grafana: 3101, 3102, 3103, ...

## Monitoring

```bash
# Check logs
docker logs --tail 50 masa_validator_1
docker logs --tail 50 masa_miner_1

# Check subnet
btcli subnet metagraph --netuid 249 --network test
```

## Cleanup

```bash
# Stop and remove containers
docker ps -a | grep 'masa_' | awk '{print $1}' | xargs -r docker stop
docker ps -a | grep 'masa_' | awk '{print $1}' | xargs -r docker rm

# Or if using Docker Compose:
docker-compose down
```

## Security

- Keep `.env` file secure (never commit it)
- Backup `.bittensor` directory regularly
- Each container uses unique ports
- Keys stored safely in `.bittensor` directory

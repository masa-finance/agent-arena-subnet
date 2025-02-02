#!/bin/bash
set -e

# Source .env if it exists
[ -f .env ] && source .env

# Export port variables explicitly
export MINER_AXON_PORT MINER_METRICS_PORT MINER_GRAFANA_PORT
export VALIDATOR_AXON_PORT VALIDATOR_METRICS_PORT VALIDATOR_GRAFANA_PORT

# Basic setup
SUBTENSOR_NETWORK=${SUBTENSOR_NETWORK:-test}
NETUID=${SUBTENSOR_NETWORK:-test}
[ "$SUBTENSOR_NETWORK" = "test" ] && NETUID="249" || NETUID="59"

echo "Starting miner for network: $SUBTENSOR_NETWORK (subnet $NETUID)"
echo "Miner count: ${MINER_COUNT:-1}"

# Debug: Print port values
echo "Port values:"
echo "MINER_GRAFANA_PORT: $MINER_GRAFANA_PORT"
echo "VALIDATOR_GRAFANA_PORT: $VALIDATOR_GRAFANA_PORT"
echo "MINER_AXON_PORT: $MINER_AXON_PORT"
echo "VALIDATOR_AXON_PORT: $VALIDATOR_AXON_PORT"

# Clean up stack (this will also remove the network)
echo "Cleaning up old stack..."
docker stack rm masa 2>/dev/null || true
sleep 2

# Pull latest image
echo "Pulling latest image..."
docker pull masaengineering/agent-arena-subnet:latest

# Create .bittensor directory
mkdir -p .bittensor
chmod 777 .bittensor

# Deploy stack
echo "Deploying stack..."
docker stack deploy -c docker-compose.yml masa --with-registry-auth

# Show services
echo "Deployed services:"
docker service ls | grep masa_

echo "Done. Check logs with: docker service logs -f masa_miner" 

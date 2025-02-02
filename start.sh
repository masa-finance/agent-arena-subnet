#!/bin/bash
set -e

# Source .env if it exists
[ -f .env ] && source .env

# Basic setup
NETWORK=${NETWORK:-test}
NETUID=${NETWORK:-test}
[ "$NETWORK" = "test" ] && NETUID="249" || NETUID="59"

echo "Starting miner for network: $NETWORK (subnet $NETUID)"
echo "Miner count: ${MINER_COUNT:-1}"

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

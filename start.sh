#!/bin/bash
set -e

# Source .env if it exists
[ -f .env ] && source .env

echo "Starting nodes for network: $SUBTENSOR_NETWORK (subnet $NETUID)"
echo "Validator count: $VALIDATOR_COUNT"
echo "Miner count: $MINER_COUNT"

# Pull latest image
echo "Pulling latest image..."
docker pull masaengineering/agent-arena-subnet:latest

# Create .bittensor directory if it doesn't exist
mkdir -p ${WALLET_PATH:-$HOME/.bittensor}
chmod 777 ${WALLET_PATH:-$HOME/.bittensor}

# Base ports
BASE_VALIDATOR_AXON_PORT=${VALIDATOR_AXON_PORT:-8142}
BASE_VALIDATOR_METRICS_PORT=${VALIDATOR_METRICS_PORT:-8001}
BASE_VALIDATOR_GRAFANA_PORT=${VALIDATOR_GRAFANA_PORT:-3001}

BASE_MINER_AXON_PORT=${MINER_AXON_PORT:-8082}
BASE_MINER_METRICS_PORT=${MINER_METRICS_PORT:-8101}
BASE_MINER_GRAFANA_PORT=${MINER_GRAFANA_PORT:-3101}

# Function to start a node
start_node() {
    local role=$1
    local instance_num=$2
    local base_axon_port=$3
    local base_metrics_port=$4
    local base_grafana_port=$5

    # Calculate ports for this instance
    local axon_port=$((base_axon_port + instance_num - 1))
    local metrics_port=$((base_metrics_port + instance_num - 1))
    local grafana_port=$((base_grafana_port + instance_num - 1))

    echo "Starting $role $instance_num with ports:"
    echo "  Axon: $axon_port"
    echo "  Metrics: $metrics_port"
    echo "  Grafana: $grafana_port"

    # Start the container
    if [ "$role" = "validator" ]; then
        ENV_VARS="-e WALLET=${WALLET} -e VALIDATOR_WALLET_NAME=${WALLET} -e VALIDATOR_HOTKEY_NAME=${role}_${instance_num}"
    else
        # For miners, check in order:
        # 1. REGISTRATION_TWEET_ID_N (for multiple miners)
        # 2. TWEET_VERIFICATION_ID (legacy)
        # 3. REGISTRATION_TWEET_ID (docker-compose compatibility)
        tweet_id_var="REGISTRATION_TWEET_ID_${instance_num}"
        tweet_id="${!tweet_id_var:-${TWEET_VERIFICATION_ID:-$REGISTRATION_TWEET_ID}}"
        ENV_VARS="-e WALLET=${WALLET} -e MINER_WALLET_NAME=${WALLET} -e MINER_HOTKEY_NAME=${role}_${instance_num} -e TWEET_VERIFICATION_ID=${tweet_id}"
    fi

    docker run -d \
        --name "masa_${role}_${instance_num}" \
        --env-file .env \
        -e ROLE=$role \
        -e NETUID=${NETUID:-59} \
        -e SUBTENSOR_NETWORK=${SUBTENSOR_NETWORK:-finney} \
        -e AXON_PORT=$axon_port \
        -e METRICS_PORT=$metrics_port \
        -e GRAFANA_PORT=$grafana_port \
        -e MINER_AXON_PORT=$axon_port \
        -e MINER_METRICS_PORT=$metrics_port \
        -e MINER_GRAFANA_PORT=$grafana_port \
        -e MINER_PORT=$axon_port \
        -e REPLICA_NUM=$instance_num \
        -e MASA_BASE_URL=https://test.protocol-api.masa.ai \
        -e API_URL=https://test.protocol-api.masa.ai \
        $ENV_VARS \
        -v $(pwd):/app \
        -v $(pwd)/.env:/app/.env \
        -v ${WALLET_PATH:-$HOME/.bittensor}:/root/.bittensor \
        -p $axon_port:$axon_port \
        -p $metrics_port:$metrics_port \
        -p $grafana_port:$grafana_port \
        masaengineering/agent-arena-subnet:latest
}

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker ps -a | grep 'masa_' | awk '{print $1}' | xargs -r docker rm -f

# Start validators
for i in $(seq 1 $VALIDATOR_COUNT); do
    start_node "validator" $i $BASE_VALIDATOR_AXON_PORT $BASE_VALIDATOR_METRICS_PORT $BASE_VALIDATOR_GRAFANA_PORT
done

# Start miners
for i in $(seq 1 $MINER_COUNT); do
    start_node "miner" $i $BASE_MINER_AXON_PORT $BASE_MINER_METRICS_PORT $BASE_MINER_GRAFANA_PORT
done

echo "All nodes started. Check logs with:"
echo "docker logs --tail 50 masa_validator_N  # where N is the validator number"
echo "docker logs --tail 50 masa_miner_N      # where N is the miner number" 

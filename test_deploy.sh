#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Function to deploy a service
deploy_service() {
    local env_file=$1
    local service_name=$2
    
    echo -e "${BLUE}Deploying $service_name using $env_file...${NC}"
    
    # Copy environment file
    cp $env_file .env
    
    # Start the service
    ./start.sh
    
    # Check deployment status
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $service_name deployed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to deploy $service_name${NC}"
        exit 1
    fi
}

# Function to check prerequisites
check_prereqs() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker is not installed${NC}"
        exit 1
    fi
    
    # Check Docker Swarm
    if ! docker info 2>&1 | grep -q "Swarm: active"; then
        echo -e "${BLUE}Initializing Docker Swarm...${NC}"
        docker swarm init
    fi
    
    echo -e "${GREEN}✓ Prerequisites checked${NC}"
}

# Main deployment flow
main() {
    echo -e "${BLUE}Starting test deployment...${NC}"
    
    # Check prerequisites
    check_prereqs
    
    # Deploy first miner
    echo -e "\n${BLUE}=== Deploying Miner 1 ===${NC}"
    deploy_service .env.miner1 "Miner 1"
    
    # Wait a bit before deploying next service
    sleep 10
    
    # Deploy second miner
    echo -e "\n${BLUE}=== Deploying Miner 2 ===${NC}"
    deploy_service .env.miner2 "Miner 2"
    
    # Wait a bit before deploying validator
    sleep 10
    
    # Deploy validator
    echo -e "\n${BLUE}=== Deploying Validator ===${NC}"
    deploy_service .env.validator "Validator"
    
    echo -e "\n${GREEN}All services deployed!${NC}"
    echo -e "\nTo check service status:"
    echo "docker service ls"
    echo -e "\nTo view logs:"
    echo "docker service logs masa_miner"
    echo "docker service logs masa_validator"
}

# Run main function
main 
#!/bin/bash
# Toolkit LLM Gateway - Deployment Script

set -e

echo " Toolkit LLM Gateway - Deployment Script"
echo "========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo " Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo " Error: Docker Compose is not installed"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    echo " Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "  Warning: No .env file found. Using defaults."
fi

# Build images
echo ""
echo " Building Docker images..."
docker-compose build

# Start services
echo ""
echo " Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo ""
echo " Waiting for services to be healthy..."
sleep 5

# Check database health
echo ""
echo " Checking PostgreSQL health..."
docker-compose exec -T postgres pg_isready -U gateway_user || {
    echo " PostgreSQL is not ready"
    exit 1
}
echo " PostgreSQL is healthy"

# Check dashboard health
echo ""
echo " Checking Dashboard health..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -f http://localhost:12000/health > /dev/null 2>&1; then
        echo " Dashboard is healthy"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo " Dashboard failed to start"
        docker-compose logs dashboard
        exit 1
    fi
    echo "Waiting for dashboard... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done

# Show running containers
echo ""
echo " Running containers:"
docker-compose ps

# Show logs
echo ""
echo " Recent logs:"
docker-compose logs --tail=20

echo ""
echo " Deployment complete!"
echo ""
echo "Dashboard: http://localhost:12000"
echo ""
echo "Useful commands:"
echo "  View logs:      docker-compose logs -f"
echo "  Stop services:  docker-compose down"
echo "  Restart:        docker-compose restart"
echo "  Remove all:     docker-compose down -v"

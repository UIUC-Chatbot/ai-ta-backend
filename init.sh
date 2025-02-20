#!/bin/bash

# USAGE: sudo sh init.sh 
# If you want to delete all your data for a fresh start, use: sudo sh init.sh --wipe_data

# Parse command line arguments
wipe_data=false
for arg in "$@"; do
  case $arg in
    --wipe_data) wipe_data=true ;;
    *) echo "Usage: $0 [--wipe_data] (use --wipe_data to delete volumes)" && exit 1 ;;
  esac
done

# Sparse checkout for supabase/docker
git submodule update --init --depth 1 --recursive && \
cd supabase && \
git sparse-checkout init --cone && \
git sparse-checkout set docker && \
cd ..

if [ ! -f ./supabase/docker/.env ]; then
  cp ./supabase/docker/.env.example ./supabase/docker/.env
fi

if [ ! -f ./ai-ta-frontend/.env ]; then
  cp .env-frontend.template ./ai-ta-frontend/.env
fi

if [ ! -f .env ]; then
  cp .env-backend.template .env
fi


set -e
# Start the Supabase Docker Compose
echo "Starting Supabase services..."
if [ "$wipe_data" = true ]; then
  docker compose -f ./supabase/docker/docker-compose.yml down -v
else
  docker compose -f ./supabase/docker/docker-compose.yml down
fi
sudo docker compose -f ./supabase/docker/docker-compose.yml up -d --build

# Wait for Supabase DB to be ready before starting Keycloak
echo "Waiting for Supabase DB to be ready..."
until docker exec supabase-db pg_isready -U postgres; do
  sleep 1
done

# Create Keycloak schema if it doesn't exist
echo "Creating Keycloak schema if it doesn't exist..."
docker exec supabase-db psql -U postgres -d postgres -c "CREATE SCHEMA IF NOT EXISTS keycloak;"

# Start the parent Docker Compose
chmod -R 777 ./supabase
echo "Starting application services..."
if [ "$wipe_data" = true ]; then
  docker compose -f ./docker-compose.yaml down -v
else
  docker compose -f ./docker-compose.yaml down
fi

# Start all services
sudo docker compose -f ./docker-compose.yaml up -d --build

echo "All services are up!"

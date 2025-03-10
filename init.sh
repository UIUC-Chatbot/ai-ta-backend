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

# Simple approach: force using HTTPS for all submodules
echo "Updating submodules using HTTPS..."
# Configure Git to use HTTPS instead of SSH just for this script
git config --global url."https://github.com/".insteadOf git@github.com:

# Initialize supabase first with depth 1 (faster, we only need part of it)
git submodule update --init --depth 1 supabase
# Set up sparse checkout for supabase
cd supabase && \
git sparse-checkout init --cone && \
git sparse-checkout set docker && \
cd ..

# Now initialize and update remaining submodules
echo "Initializing and updating other submodules..."
git submodule update --init --remote --recursive

if [ ! -f ./supabase/docker/.env ]; then
  cp ./supabase/docker/.env.example ./supabase/docker/.env
fi

if [ ! -f ./uiuc-chat-frontend/.env ]; then
  cp .env-frontend.template ./uiuc-chat-frontend/.env
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
sudo docker compose -f ./supabase/docker/docker-compose.yml -f ./docker-compose.override.yml up -d --build

# Wait for Supabase DB to be ready before starting Keycloak
echo "Waiting for Supabase DB to be ready..."
until docker exec supabase-db pg_isready -U postgres; do
  echo "Database not yet ready - waiting..."
  sleep 2
done

until docker exec supabase-db psql -U postgres -c "SELECT 1" >/dev/null 2>&1; do
  echo "Testing database connection - waiting..."
  sleep 2
done

# Create required schemas for Realtime service
echo "Creating required schemas for Realtime..."
docker exec supabase-db psql -U postgres -d postgres -c "CREATE SCHEMA IF NOT EXISTS realtime;"
docker exec supabase-db psql -U postgres -d postgres -c "CREATE SCHEMA IF NOT EXISTS _realtime;"
docker exec supabase-db psql -U postgres -d postgres -c "GRANT USAGE ON SCHEMA realtime TO supabase_admin, postgres, authenticator;"
docker exec supabase-db psql -U postgres -d postgres -c "GRANT USAGE ON SCHEMA _realtime TO supabase_admin, postgres, authenticator;"

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

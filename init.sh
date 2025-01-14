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

if [ ! -f .env ]; then
  cp .env.template .env
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

# Wait for the database to be ready
# echo "Waiting for the database to be ready..."
# until docker exec supabase-db pg_isready -U postgres; do
#   sleep 1
# done

# Start the parent Docker Compose
chmod -R 777 ./supabase
echo "Starting application services..."
if [ "$wipe_data" = true ]; then
  docker compose -f ./docker-compose.yaml down -v
else
  docker compose -f ./docker-compose.yaml down
fi
# Note: you may need to give docker with sufficient permissions to run this command (eg: sudo chmod -r 777 .)
sudo docker compose -f ./docker-compose.yaml up -d --build

echo "All services are up!"
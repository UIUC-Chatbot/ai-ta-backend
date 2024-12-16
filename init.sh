#!/bin/bash

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
docker compose -f ./supabase/docker/docker-compose.yml down -v
docker compose -f ./supabase/docker/docker-compose.yml -f ./docker-compose.override.yml up -d

# Wait for the database to be ready
echo "Waiting for the database to be ready..."
until docker exec supabase-db pg_isready -U postgres; do
  sleep 1
done

# Start the parent Docker Compose
echo "Starting application services..."
docker compose -f ./docker-compose.yaml down -v
docker compose -f ./docker-compose.yaml up -d

echo "All services are up!"
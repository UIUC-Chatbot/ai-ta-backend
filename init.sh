#!/bin/bash

git submodule update --init --recursive

if [ ! -f ./supabase/docker/.env ]; then
  cp ./supabase/docker/.env.example ./supabase/docker/.env
fi
set -e

# Start the Supabase Docker Compose
echo "Starting Supabase services..."
docker compose -f ./supabase/docker/docker-compose.yml -f ./docker-compose.override.yml up -d

# Wait for the database to be ready
echo "Waiting for the database to be ready..."
until docker exec supabase-db pg_isready -U postgres; do
  sleep 1
done

# Start the parent Docker Compose
echo "Starting application services..."
docker compose -f ./docker-compose.yaml up -d

echo "All services are up!"
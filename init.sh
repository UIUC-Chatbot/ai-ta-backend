### To Run the script:
### chmod +x init.sh
### ./init.sh

#!/bin/bash
set -e

# Start the Supabase Docker Compose
echo "Starting Supabase services..."
docker compose -f ./supabase/docker/docker-compose.yml up -d

# Start the parent Docker Compose
echo "Starting application services..."
docker compose -f ./docker-compose.yaml up -d

echo "All services are up!"

#!/bin/bash

# Starting with Redis Queue. Just run this script!
# ./run-dev.sh

# Function to clean up processes on exit
cleanup() {
	echo "Cleaning up processes..."
	kill $(lsof -t -i:9181) 2>/dev/null
	kill $WORKER_PID 2>/dev/null
	kill $FLASK_PID 2>/dev/null
	exit 0
}

# Set up trap to catch SIGTERM and other signals
trap cleanup SIGTERM SIGINT SIGQUIT

export PYTHONPATH=${PYTHONPATH}:$(pwd)/ai_ta_backend
# To start the dashboard -- the problem is shutting it down propery on SIGTERM
infisical run --env=dev -- bash -c 'echo "REDIS URL -- redis://:$INGEST_REDIS_PASSWORD@$INGEST_REDIS_HOST:$INGEST_REDIS_PORT"'
infisical run --env=dev -- bash -c 'rq-dashboard --redis-url "redis://:$INGEST_REDIS_PASSWORD@$INGEST_REDIS_HOST:$INGEST_REDIS_PORT"' &

infisical run --env=dev -- python3 ai_ta_backend/redis_queue/worker.py &
infisical run --env=dev -- flask --app ai_ta_backend.main:app --debug run --port 8000

#!/bin/bash

# Starting with Redis Queue. Just run this script!
# ./run-dev.sh

export INGEST_REDIS_PASSWORD=MBSCar1pkEVSRfQNuM1OTxuTtIVETuCRcVz24B8yYI39fY7ZCPYUj8sgHZ1ALxsB
export INGEST_REDIS_URL=dankchat.humpback-symmetric.ts.net
export INGEST_REDIS_PORT=6701


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
bash -c 'echo "REDIS URL -- redis://:$INGEST_REDIS_PASSWORD@$INGEST_REDIS_URL:$INGEST_REDIS_PORT"'
bash -c 'rq-dashboard --redis-url "redis://:$INGEST_REDIS_PASSWORD@$INGEST_REDIS_URL:$INGEST_REDIS_PORT"' &


python3 ai_ta_backend/redis_queue/worker.py &
flask --app ai_ta_backend.main:app --debug run --port 8000

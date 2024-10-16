#!/bin/bash

# Docs https://docs.gunicorn.org/en/stable/settings.html#workers

# 200 MB object store memory.. necessary to statically allocate or will crash in Railway env restrictions.
# ray start --head --num-cpus 6 --object-store-memory 300000000
export PYTHONPATH=${PYTHONPATH}:$(pwd)/ai_ta_backend

# Function to clean up processes on exit
cleanup() {
    echo "Cleaning up processes..."
    kill $WORKER_PID 2>/dev/null
    kill $GUNICORN_PID 2>/dev/null
    exit 0
}

# Set up trap to catch SIGTERM and other signals
trap cleanup SIGTERM SIGINT SIGQUIT

# Start Redis Queue worker
python3 ai_ta_backend/redis_queue/worker.py &
WORKER_PID=$!

# Start Gunicorn server
exec gunicorn --workers=3 --threads=100 --worker-class=gthread ai_ta_backend.main:app --timeout 1800 &
GUNICORN_PID=$!

# Wait for processes to finish
wait $GUNICORN_PID

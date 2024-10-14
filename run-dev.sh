#!/bin/bash

# Docs https://docs.gunicorn.org/en/stable/settings.html#workers

# Starting with Redis Queue
# 1. redis-server -- Start Redis
# 2. ./run-dev.sh  --  Run this script
# 3. python ai_ta_backend/redis_queue/worker.py -- Start the workers

export PYTHONPATH=${PYTHONPATH}:$(pwd)/ai_ta_backend
infisical run --env=dev -- flask --app ai_ta_backend.main:app --debug run --port 8000

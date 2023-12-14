#!/bin/bash

# Docs https://docs.gunicorn.org/en/stable/settings.html#workers

pip list

# 500 MB memory
ray start --head --num-cpus=8 --object-store-memory=200000000
export PYTHONPATH=${PYTHONPATH}:$(pwd)/ai_ta_backend
exec gunicorn --workers=3 --threads=16 --worker-class=gthread ai_ta_backend.main:app --timeout 1800

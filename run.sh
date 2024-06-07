#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)/ai_ta_backend
ray start --head --num-cpus 1 --object-store-memory 400000000
exec gunicorn --workers=1 --threads=10 --worker-class=gthread ai_ta_backend.main:app --timeout 1800
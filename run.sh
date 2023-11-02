#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)/ai_ta_backend
exec newrelic-admin run-program gunicorn --workers=6 --threads=6 --worker-class=gthread ai_ta_backend.main:app --timeout 108000
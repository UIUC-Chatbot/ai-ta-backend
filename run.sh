#!/bin/bash

# Docs https://docs.gunicorn.org/en/stable/settings.html#workers

export PYTHONPATH=$PYTHONPATH:$(pwd)/ai_ta_backend
exec gunicorn --workers=3 --threads=10 --worker-class=gthread ai_ta_backend.main:app --timeout 60 --max-requests 2
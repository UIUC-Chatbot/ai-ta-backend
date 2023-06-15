#!/bin/bash

export PYTHONPATH=$PYTHONPATH:$(pwd)/ai_ta_backend
exec gunicorn ai_ta_backend.main:app --timeout 108000
#!/bin/bash

echo "Starting Celery Worker..."

cd /usr/src/fastapi

celery -A celery_background.app worker --loglevel=info --concurrency=2
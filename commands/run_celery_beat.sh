#!/bin/bash

echo "Starting Celery Beat..."

cd /usr/src/fastapi

rm -f celerybeat.pid

celery -A celery_app beat --loglevel=info
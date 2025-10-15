#!/bin/bash

# Exit the script immediately if any command exits with a non-zero status
set -e

# Function to handle errors with custom messages
handle_error() {
    echo "Error: $1"
    exit 1
}

# Navigate to the application directory
cd /home/ubuntu/src/online-cinema-api || handle_error "Failed to navigate to the application directory."

# get deploy branch from environments
BRANCH=${DEPLOY_BRANCH:-main}
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# Fetch the latest changes from the remote repository
echo "Fetching the latest changes from the remote repository..."
git fetch origin "$BRANCH" || handle_error "Failed to fetch updates from the 'origin' remote."

# checkout to deploy branch
git checkout $BRANCH

# Reset the local repository to match the remote 'main' branch
echo "Resetting the local repository to match 'origin/main'..."
git reset --hard "origin/$BRANCH" || handle_error "Failed to reset the local repository to 'origin/'."

# stop all active docker containers
docker stop $(docker ps -q)

# delete all previous docker containers
docker container prune -f

# (Optional) Pull any new tags from the remote repository
echo "Fetching tags from the remote repository..."
git fetch origin --tags || handle_error "Failed to fetch tags from the 'origin' remote."

# Build and run Docker containers with Docker Compose v2
docker compose -f docker-compose-prod.yml up -d --build || handle_error "Failed to build and run Docker containers using docker-compose-prod.yml."

# Print a success message upon successful deployment
echo "Deployment completed successfully."

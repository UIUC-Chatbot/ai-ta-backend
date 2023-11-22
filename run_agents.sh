#!/bin/bash

# ensure env is up to date
rm -f ./ai_ta_backend/agents/.env
cp .env ai_ta_backend/agents/.env

# Function to handle script termination
cleanup() {
    pkill -P $$  # Kill all child processes
    exit 255
}
# Set trap for catching Ctrl+C and script termination
trap cleanup SIGINT SIGTERM

# start docker if it's not running
if ! pgrep -f Docker.app > /dev/null; then
    echo "Starting Docker... please hang tight while it get's started for you."
    open -a "Docker"
    while ! docker ps > /dev/null 2>&1; do
        sleep 1
    done
    echo "✅ Docker is now running"
elif [ $(uname) = "Linux" ]; then
    docker ps > /dev/null 2>&1
    if [ ! $? -eq 0 ]; then
        # docker is NOT running
        echo "Docker is NOT running, please start Docker."
        # my attempts were unreliable... especially with WSL2.
        sudo service docker start
        sudo systemctl start docker
    fi 
fi

# Re-install our Langchain fork (not too slow, so might as well)
# echo "Re-Installing Langchain fork to ensure it's updated..."
# pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain&subdirectory=libs/langchain"
# pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain-experimental&subdirectory=libs/experimental"

#! WORK IN PROGRESS -- Checking if Langchain is up to date
# Get the latest commit hash from the repository
# latest_commit=$(git ls-remote https://github.com/KastanDay/langchain-improved-agents.git | head -1 | awk '{print $1}')
# # Get the installed version
# installed_version=$(pip show langchain | grep Version | awk '{print $2}')
# # Extract the commit hash from the installed version
# installed_commit=${installed_version#*-}
# # Check if the installed commit hash is the latest
# if [ "$installed_commit" != "$latest_commit" ]; then
#     echo "Re-Installing Langchain fork to ensure it's updated..."
#     pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain&subdirectory=libs/langchain"
#     pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain-experimental&subdirectory=libs/experimental"
# else
#     echo "Langchain is up to date."
# fi

# Start port forwarding
# smee -u https://smee.io/nRnJDGnCbWYUaSGg --port 8000 &

# Start Flask (with New Relic logging)
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program flask --app ai_ta_backend.main:app --debug run --port 8000

# echo "✅ READY TO USE!"
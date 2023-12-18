#!/bin/bash

echo "⚠️  Activate your ** VIRTUAL ENVIRONMENT ** before running this script!"

# Function to handle script termination
cleanup() {
    echo "🧹 Cleaning up..."
    pkill -P $$  # Kill all child processes
    pkill -f "flask --app ai_ta_backend.main:app --debug run --port 8000"  # Kill Flask process
    exit 255
}
# Set trap for catching Ctrl+C and script termination
trap cleanup SIGINT SIGTERM

#! Check if langchain is up to date with latest commit on branch `uiuc-dot-chat` of https://github.com/KastanDay/langchain-improved-agents.git 
# Get the latest commit hash from the repository
latest_commit=$(git ls-remote https://github.com/KastanDay/langchain-improved-agents.git uiuc-dot-chat | head -1 | awk '{print $1}')
# Get the installed version
installed_version=$(pip freeze | grep langchain)
# Extract the commit hash from the installed version
installed_commit=${installed_version#*@}
installed_commit=${installed_commit%%#*}
installed_commit=${installed_commit##*.git@}
echo "Langchain Installed commit: $installed_commit"
echo "Langchain Latest commit: $latest_commit"

# Check if the installed commit hash is the latest
if [ "$installed_commit" != "$latest_commit" ]; then
    echo "Re-Installing Langchain fork to ensure it's updated..."
    pip uninstall langchain langchain-experimental -y
    pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain&subdirectory=libs/langchain"
    pip install "git+https://github.com/KastanDay/langchain-improved-agents.git@uiuc-dot-chat#egg=langchain-experimental&subdirectory=libs/experimental"
else
    echo "Langchain is up to date."
fi

# Start port forwarding if no other instances of smee are already running
if ! pgrep -f smee > /dev/null; then
    smee -u https://smee.io/nRnJDGnCbWYUaSGg --port 8000 &
fi

# Start Flask (with New Relic logging) in the background
flask --app ai_ta_backend.main:app --debug run --port 8000 &

# Keep script running
while true; do
    sleep 1
done
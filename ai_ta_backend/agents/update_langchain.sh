#!/bin/bash

echo " 👉 Updating Langchain if necessary (inside Docker)"

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

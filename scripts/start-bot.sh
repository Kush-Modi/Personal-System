#!/data/data/com.termux/files/usr/bin/bash

# Startup script for Termux boot

termux-wake-lock

cd ~/personal-server || exit 1

echo "$(date) - Starting network watcher..."

tmux has-session -t network-watch 2>/dev/null || \
tmux new-session -d -s network-watch \
"cd ~/personal-server && ./network-watch.sh"

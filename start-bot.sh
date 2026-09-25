#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock

# Start SSH daemon if not already running (idempotent)
if ! pgrep -x sshd > /dev/null 2>&1; then
    sshd
    echo "$(date) - sshd started."
else
    echo "$(date) - sshd already running."
fi

cd ~/personal-server || exit 1

echo "$(date) - Starting network watcher..."

tmux has-session -t network-watch 2>/dev/null || \
tmux new-session -d -s network-watch \
"cd ~/personal-server && ./network-watch.sh"
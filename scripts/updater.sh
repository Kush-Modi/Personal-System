#!/data/data/com.termux/files/usr/bin/bash

# Hardened Transactional Updater for Personal-System

set -o pipefail

cd ~/personal-server || {
    echo "$(date) - ERROR: Failed to navigate to ~/personal-server"
    exit 1
}

echo "$(date) - Checking GitHub..."

if ! git fetch origin main; then
    echo "$(date) - ERROR: 'git fetch' failed. Network issue or remote unavailable. Keeping current bot running."
    exit 1
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null)

if [ -z "$LOCAL" ] || [ -z "$REMOTE" ]; then
    echo "$(date) - ERROR: Could not determine git revisions."
    exit 1
fi

if [ "$LOCAL" != "$REMOTE" ]; then

    echo "$(date) - New code detected ($LOCAL -> $REMOTE). Updating..."

    if ! git pull --ff-only origin main; then
        echo "$(date) - ERROR: 'git pull --ff-only' failed. Deployment aborted. Bot will NOT be stopped."
        exit 1
    fi

    echo "$(date) - Installing boot script..."

    mkdir -p ~/.termux/boot
    if [ -f ~/personal-server/start-bot.sh ]; then
        cp ~/personal-server/start-bot.sh ~/.termux/boot/start-bot
        chmod +x ~/.termux/boot/start-bot
    fi

    echo "$(date) - Restarting bot..."

    tmux kill-session -t bot 2>/dev/null

    echo "$(date) - Bot stopped. Network watcher will restart it when Telegram is reachable."
    echo "$(date) - Update complete."

else
    echo "$(date) - No update."
fi

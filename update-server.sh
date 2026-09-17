#!/data/data/com.termux/files/usr/bin/bash

cd ~/personal-server || exit 1

echo "$(date) - Checking GitHub..."

git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then

    echo "$(date) - New code detected. Updating..."

    git pull --ff-only origin main

    echo "$(date) - Installing boot script..."

    mkdir -p ~/.termux/boot
    cp ~/personal-server/start-bot.sh ~/.termux/boot/start-bot
    chmod +x ~/.termux/boot/start-bot

    echo "$(date) - Restarting bot..."

    tmux kill-session -t bot 2>/dev/null

    ~/personal-server/start-bot.sh

    echo "$(date) - Update complete."

else
    echo "$(date) - No update."
fi
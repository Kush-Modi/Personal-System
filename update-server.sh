#!/data/data/com.termux/files/usr/bin/bash

cd ~/personal-server || exit 1

git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "New code detected. Updating..."

    git pull --ff-only origin main

    echo "Restarting bot..."

    tmux kill-session -t bot 2>/dev/null

    tmux new-session -d -s bot \
        "cd ~/personal-server && source venv/bin/activate && python bot.py"

    echo "Update complete."
else
    echo "No update."
fi

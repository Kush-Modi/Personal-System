#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock

cd ~/personal-server || exit 1

echo "$(date) - Waiting for Telegram network..."

while ! curl -4 -fsS --max-time 5 https://api.telegram.org >/dev/null 2>&1; do
    sleep 10
done

echo "$(date) - Telegram network available."

if tmux has-session -t bot 2>/dev/null; then
    echo "$(date) - Bot already running."
    exit 0
fi

echo "$(date) - Starting bot..."

tmux new-session -d -s bot \
    "cd ~/personal-server && source venv/bin/activate && python bot.py"

echo "$(date) - Bot started."
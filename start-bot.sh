#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock

cd ~/personal-server || exit 1

echo "$(date) - Starting network watcher..."

while true; do

    # If bot is already running, just wait and check again later
    if tmux has-session -t bot 2>/dev/null; then
        sleep 30
        continue
    fi

    # Check whether Telegram is reachable over IPv4
    if curl -4 -fsS --max-time 5 https://api.telegram.org >/dev/null 2>&1; then

        echo "$(date) - Telegram reachable. Starting bot..."

        tmux new-session -d -s bot \
            "cd ~/personal-server && source venv/bin/activate && python bot.py"

        sleep 30

    else

        echo "$(date) - Telegram unavailable. Retrying in 10 seconds..."

        sleep 10
    fi

done
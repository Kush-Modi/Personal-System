# Personal-System

A self-hosted, modular personal assistant running on Android (Termux) and developed on Windows / GitHub.

---

## 🏛 Architecture

Personal-System follows a layered, modular architecture:

```
Telegram Handlers / Router
        ↓
    Services  (Business Logic)
        ↓
  Repositories (Persistence Abstraction)
        ↓
 SQLite (WAL mode, Foreign Keys)
```

### Directory Structure

```
Personal-System/
├── app/
│   ├── ai/                  # AI providers and perception abstractions (Gemini/Local)
│   ├── core/                # Centralized config, structured logging, health checks, exceptions
│   ├── database/            # Connection manager, schema migrations, repositories
│   ├── services/            # Business services (Food, Weight, Finance, System)
│   └── telegram/            # Bot entrypoint, router, keyboards, command & message handlers
├── data/                    # Storage for cached data and incoming images
├── logs/                    # Rotating application logs
├── scripts/                 # Termux automation scripts (updater, network watcher, boot)
├── tests/                   # Automated unit test suite
├── .env.example             # Example configuration
├── requirements.txt         # Dependencies
├── bot.py                   # Root entrypoint shim (for Termux backward compatibility)
└── database.py              # Root database shim
```

---

## 🚀 Features

### 🍽 Food Tracking
- `/food NAME CALORIES` — Log food with calories (e.g. `/food burrito 650`)
- `/food` — View today's food log and total calories
- `/food yesterday` or `/food 2026-09-01` — View food log for a specific date
- `/food edit NUMBER NAME CALORIES` — Edit food entry by index
- `/food delete NUMBER [date]` — Delete food entry by index

### ⚖️ Weight Tracking
- `/weight NUMBER` — Log or update today's weight (e.g. `/weight 75.5`)
- `/weight` — View last 30 weight records
- `/weight yesterday` or `/weight 2026-09-01` — View weight for a specific date
- `/weight delete [date]` — Delete weight record for date

### 📊 Summary & Reports
- `/summary [date]` — Overview of food count, total calories, and weight
- `/weekly [date]` — Full weekly report (Monday to Sunday) with weight changes and calorie averages
- `/monthly [YYYY-MM]` — Monthly report with daily breakdowns and averages

### 🖥 System Status
- `/status` — Real-time health diagnostic (Database integrity, disk space, network reachability, uptime)

---

## 🛠 Deployment & Setup (Android Termux)

1. **Environment Setup:**
   ```bash
   pkg update && pkg install python git tmux curl
   cd ~/personal-server
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration:**
   ```bash
   cp .env.example .env
   nano .env # Set TELEGRAM_BOT_TOKEN
   ```

3. **Running Database Migrations:**
   Migrations execute automatically on bot startup, or can be run manually:
   ```bash
   python database.py
   ```

4. **Starting the Bot & Network Watcher:**
   ```bash
   ./start-bot.sh
   ```

5. **Automatic Updates:**
   The phone checks GitHub via `watch-updates.sh` or `update-server.sh` every 5 minutes. The hardened updater ensures zero downtime on fetch/pull failures.

---

## 🧪 Testing

Run the automated test suite locally:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

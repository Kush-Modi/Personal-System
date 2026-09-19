# Personal-System

A self-hosted, modular personal assistant running on Android (Termux) and developed on Windows / GitHub.

---

## 🏛 Architecture

Personal-System follows a layered, deterministic-first architecture:

```
                    ┌──────────────┐
                    │   Telegram   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Input Router │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
          Command        Text         Photo
              │            │            │
              │            ▼            ▼
              │      Input Processor   Image Processor
              │            │            │
              └────────────┴────────────┘
                           │
                    Structured Result
                           │
                    ┌──────▼───────┐
                    │  Validation  │ (Level 1 Schema + Level 2 Domain)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Pending Item │ (SQLite Staging Table)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
           [Save]       [Edit]      [Reject]
              │            │            │
              │            ▼            │
              │      Edit Session       │
              │      (Validates new)    │
              │            │            │
              └────────────┼────────────┘
                           ▼
                     Domain Service
                           │
                       Repository
                           │
                      SQLite DB (WAL Mode)
```

---

## 📂 Project Structure

```
Personal-System/
├── app/
│   ├── ai/                  # AI provider abstractions (Gemini/Local provider interfaces)
│   ├── core/                # Config, structured logging, health checks, exceptions
│   ├── database/            # SQLite connection (WAL mode), migrations, repositories
│   │   └── repositories/    # Food, Weight, Expense, PendingItem, EditSession
│   ├── domain/              # Domain models (ItemType, PendingItem, Payloads), Validators
│   ├── input/               # ProcessingResult, InputProcessor, MockInputProcessor
│   ├── media/               # MediaStorage, Image Optimizer (Pillow), Retention Cleanup
│   ├── services/            # Business services (Food, Weight, Finance, Pending, System, Review)
│   └── telegram/            # Router, keyboards, renderers, sessions, command/message/photo handlers
├── data/                    # Managed storage for media & cache
├── logs/                    # Rotating application logs
├── scripts/                 # Termux automation scripts (updater, network watcher, boot)
├── tests/                   # Automated unit & integration test suite (52 tests)
├── .env.example             # Example configuration template
├── requirements.txt         # Dependencies (python-telegram-bot, python-dotenv, pillow)
├── bot.py                   # Root entrypoint shim (for Termux backward compatibility)
└── database.py              # Root database shim (runs migrations safely)
```

---

## 🔄 Phase 2 Pending Item & Confirmation Lifecycle

1. **Input Ingestion**: Text or photos are parsed via `InputProcessor` into a typed `ProcessingResult`.
2. **Two-Level Validation**:
   - **Level 1 (Schema)**: Ensures required fields exist and types are valid.
   - **Level 2 (Domain)**: Enforces business constraints (e.g. food calories > 0 and <= 10,000).
3. **Pending Item Staging**: Validated items are staged in the `pending_items` SQLite table with state `PENDING`.
4. **Interactive Telegram UI**:
   - `[✅ Save]` — Validates and invokes domain service (`FoodService`, `FinanceService`), marks item `CONFIRMED`. Guaranteed idempotent against double-clicks.
   - `[✏️ Edit]` — Initiates a short-lived interactive edit session. User sends corrections, the payload updates, and a fresh preview is rendered for final confirmation (editing **never** auto-saves).
   - `[❌ Reject]` — Marks item `REJECTED` and discards.
5. **Media Optimization & Retention**:
   - Inbound images are compressed, resized (max 1600px), stripped of EXIF, and stored locally in `data/images/`.
   - Automatic retention cleanup (default 30 days) runs safely and **protects active pending images** from deletion.
6. **End-of-Day Review**:
   - Evaluates pending items at review time. If 0 items are pending, **no message is sent**. If >0 items are pending, a concise summary is delivered.

---

## 🚀 Features & Commands

### 🍽 Food Tracking
- `/food NAME CALORIES` — Log food directly (e.g. `/food burrito 650`)
- `/food` — View today's food log and total calories
- `/food yesterday` or `/food 2026-09-01` — View food log for a specific date
- `/food edit NUMBER NAME CALORIES` — Edit food entry by daily index
- `/food delete NUMBER [date]` — Delete food entry by daily index

### ⚖️ Weight Tracking
- `/weight NUMBER` — Log or update today's weight (e.g. `/weight 75.5`)
- `/weight` — View last 30 weight records
- `/weight yesterday` or `/weight 2026-09-01` — View weight for a specific date
- `/weight delete [date]` — Delete weight record for date

### 📊 Reports & Diagnostics
- `/summary [date]` — Daily overview of food count, total calories, and weight
- `/weekly [date]` — Monday to Sunday report with weight delta and calorie averages
- `/monthly [YYYY-MM]` — Monthly report with day-by-day breakdowns
- `/status` — Real-time health diagnostic (Database, disk storage, Telegram network, uptime)
- `/pending` — Review all active items waiting for confirmation

### 🧪 Mock AI Testing Commands
- `mock food Paneer Tikka 420` — Test food AI extraction & confirmation workflow
- `mock expense 1250 Shopping Amazon` — Test expense extraction workflow
- `mock task Submit project report` — Test task extraction workflow
- Send any photo — Tests photo optimization, local storage, and mock perception

---

## 🛠 Deployment & Setup (Android Termux)

1. **Install Dependencies:**
   ```bash
   pkg update && pkg install python git tmux curl libjpeg-turbo
   cd ~/personal-server
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run Database Migrations:**
   ```bash
   python database.py
   ```

3. **Start Bot:**
   ```bash
   ./start-bot.sh
   ```

---

## 🧪 Testing

Run all unit, repository, service, and end-to-end integration tests:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

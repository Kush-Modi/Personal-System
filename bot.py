import socket

# Force IPv4 because IPv6 connectivity is unreliable on this network
_original_getaddrinfo = socket.getaddrinfo


def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(
        host,
        port,
        socket.AF_INET,
        type,
        proto,
        flags
    )


socket.getaddrinfo = getaddrinfo_ipv4


import os
import sqlite3
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# ==================================================
# CONFIGURATION
# ==================================================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

DB_PATH = "personal.db"


# ==================================================
# DATABASE
# ==================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


# ==================================================
# DATE HELPERS
# ==================================================

def today_date():
    return datetime.now().date()


def parse_date(value):
    """
    Supports:
    today
    yesterday
    YYYY-MM-DD
    """

    today = today_date()

    if not value:
        return today, "Today"

    value = value.strip().lower()

    if value == "today":
        return today, "Today"

    if value == "yesterday":
        return today - timedelta(days=1), "Yesterday"

    try:
        date = datetime.strptime(value, "%Y-%m-%d").date()
        return date, date.strftime("%d %b %Y")

    except ValueError:
        return None, None


def format_date(date):
    return date.isoformat()


def date_error():
    return (
        "Invalid date.\n\n"
        "Use:\n"
        "today\n"
        "yesterday\n"
        "YYYY-MM-DD"
    )


# ==================================================
# START / HELP
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = (
        "🤖 Personal Server\n\n"

        "🍽 FOOD\n"
        "/food NAME CALORIES\n"
        "/food\n"
        "/food yesterday\n"
        "/food 2026-09-01\n\n"

        "Edit food:\n"
        "/food edit NUMBER NAME CALORIES\n\n"

        "Delete food:\n"
        "/food delete NUMBER\n\n"

        "⚖️ WEIGHT\n"
        "/weight NUMBER\n"
        "/weight\n"
        "/weight yesterday\n"
        "/weight 2026-09-01\n\n"

        "📊 SUMMARY\n"
        "/summary\n"
        "/summary yesterday\n\n"

        "📈 REPORTS\n"
        "/weekly\n"
        "/weekly 2026-09-01\n\n"
        "/monthly\n"
        "/monthly 2026-09"
    )

    await update.message.reply_text(message)


# ==================================================
# FOOD HELPERS
# ==================================================

def get_food_for_date(date):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, food_name, calories
        FROM food
        WHERE DATE(created_at, 'localtime') = ?
        ORDER BY id ASC
        """,
        (format_date(date),)
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


# ==================================================
# FOOD COMMAND
# ==================================================

async def food(update: Update, context: ContextTypes.DEFAULT_TYPE):

    args = context.args

    # ----------------------------------------------
    # VIEW FOOD
    # ----------------------------------------------

    if not args:

        date = today_date()
        await show_food(update, date, "Today")
        return


    # ----------------------------------------------
    # VIEW SPECIFIC DATE
    # ----------------------------------------------

    if len(args) == 1:

        date, label = parse_date(args[0])

        if date:

            await show_food(update, date, label)
            return


    # ----------------------------------------------
    # DELETE
    # ----------------------------------------------

    if args[0].lower() == "delete":

        await delete_food(update, args[1:])
        return


    # ----------------------------------------------
    # EDIT
    # ----------------------------------------------

    if args[0].lower() == "edit":

        await edit_food(update, args[1:])
        return


    # ----------------------------------------------
    # ADD FOOD
    # ----------------------------------------------

    if len(args) < 2:

        await update.message.reply_text(
            "Usage:\n"
            "/food NAME CALORIES"
        )

        return

    try:

        calories = float(args[-1])

        food_name = " ".join(args[:-1])

        if calories <= 0 or calories > 10000:

            raise ValueError

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO food (food_name, calories)
            VALUES (?, ?)
            """,
            (food_name, calories)
        )

        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"🍽 Added: {food_name}\n"
            f"🔥 {calories:.0f} kcal"
        )

    except ValueError:

        await update.message.reply_text(
            "Usage:\n"
            "/food NAME CALORIES\n\n"
            "Example:\n"
            "/food veg burrito 650"
        )


# ==================================================
# SHOW FOOD
# ==================================================

async def show_food(update, date, label):

    rows = get_food_for_date(date)

    if not rows:

        await update.message.reply_text(
            f"No food recorded for {label}."
        )

        return

    message = f"🍽 {label}\n\n"

    total = 0

    for number, (_, name, calories) in enumerate(rows, start=1):

        total += calories

        message += (
            f"{number}. {name} — "
            f"{calories:.0f} kcal\n"
        )

    message += (
        f"\n━━━━━━━━━━\n"
        f"🔥 Total: {total:.0f} kcal"
    )

    await update.message.reply_text(message)


# ==================================================
# DELETE FOOD
# ==================================================

async def delete_food(update, args):

    if not args:

        await update.message.reply_text(
            "Usage:\n"
            "/food delete NUMBER"
        )

        return

    try:

        number = int(args[0])

        date = today_date()

        if len(args) > 1:

            date, label = parse_date(args[1])

            if not date:

                await update.message.reply_text(
                    date_error()
                )

                return

        rows = get_food_for_date(date)

        if number < 1 or number > len(rows):

            await update.message.reply_text(
                "Food entry not found."
            )

            return

        database_id = rows[number - 1][0]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM food WHERE id = ?",
            (database_id,)
        )

        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"🗑️ Food entry {number} deleted."
        )

    except ValueError:

        await update.message.reply_text(
            "Please enter a valid number."
        )


# ==================================================
# EDIT FOOD
# ==================================================

async def edit_food(update, args):

    if len(args) < 3:

        await update.message.reply_text(
            "Usage:\n"
            "/food edit NUMBER NAME CALORIES\n\n"
            "Example:\n"
            "/food edit 2 veg burrito 550"
        )

        return

    try:

        number = int(args[0])

        calories = float(args[-1])

        food_name = " ".join(args[1:-1])

        if number < 1 or calories <= 0:

            raise ValueError

        date = today_date()

        rows = get_food_for_date(date)

        if number > len(rows):

            await update.message.reply_text(
                "Food entry not found."
            )

            return

        database_id = rows[number - 1][0]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE food
            SET food_name = ?, calories = ?
            WHERE id = ?
            """,
            (
                food_name,
                calories,
                database_id
            )
        )

        conn.commit()
        conn.close()

        await update.message.reply_text(
            f"✏️ Food entry {number} updated.\n\n"
            f"{food_name}\n"
            f"🔥 {calories:.0f} kcal"
        )

    except ValueError:

        await update.message.reply_text(
            "Invalid input."
        )


# ==================================================
# WEIGHT
# ==================================================

async def weight(update: Update, context: ContextTypes.DEFAULT_TYPE):

    args = context.args


    # ----------------------------------------------
    # SHOW HISTORY
    # ----------------------------------------------

    if not args:

        await show_weights(update)
        return


    # ----------------------------------------------
    # DELETE
    # ----------------------------------------------

    if args[0].lower() == "delete":

        await delete_weight(update, args[1:])
        return


    # ----------------------------------------------
    # VIEW SPECIFIC DATE
    # ----------------------------------------------

    date, label = parse_date(args[0])

    if date:

        await show_weight_date(
            update,
            date,
            label
        )

        return


    # ----------------------------------------------
    # SAVE / UPDATE WEIGHT
    # ----------------------------------------------

    try:

        weight_value = float(args[0])

        if weight_value <= 0 or weight_value > 500:

            raise ValueError

        today = format_date(today_date())

        conn = get_connection()
        cursor = conn.cursor()

        # Check whether today's weight exists
        cursor.execute(
            """
            SELECT id
            FROM weights
            WHERE DATE(created_at, 'localtime') = ?
            """,
            (today,)
        )

        existing = cursor.fetchone()

        if existing:

            cursor.execute(
                """
                UPDATE weights
                SET weight = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    weight_value,
                    existing[0]
                )
            )

            message = (
                f"⚖️ Today's weight updated: "
                f"{weight_value:.1f} kg"
            )

        else:

            cursor.execute(
                """
                INSERT INTO weights (weight)
                VALUES (?)
                """,
                (weight_value,)
            )

            message = (
                f"⚖️ Weight saved: "
                f"{weight_value:.1f} kg"
            )

        conn.commit()
        conn.close()

        await update.message.reply_text(message)

    except ValueError:

        await update.message.reply_text(
            "Usage:\n"
            "/weight 75.5"
        )


# ==================================================
# SHOW WEIGHT HISTORY
# ==================================================

async def show_weights(update):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT weight, created_at
        FROM weights
        ORDER BY DATE(created_at, 'localtime') DESC
        LIMIT 30
        """
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "No weight records yet."
        )

        return

    message = "⚖️ Weight History\n\n"

    for weight_value, created_at in rows:

        date = created_at[:10]

        message += (
            f"{date} — "
            f"{weight_value:.1f} kg\n"
        )

    await update.message.reply_text(message)


# ==================================================
# SHOW WEIGHT BY DATE
# ==================================================

async def show_weight_date(update, date, label):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT weight
        FROM weights
        WHERE DATE(created_at, 'localtime') = ?
        """,
        (format_date(date),)
    )

    row = cursor.fetchone()

    conn.close()

    if not row:

        await update.message.reply_text(
            f"No weight recorded for {label}."
        )

        return

    await update.message.reply_text(
        f"⚖️ {label}\n\n"
        f"{row[0]:.1f} kg"
    )


# ==================================================
# DELETE WEIGHT
# ==================================================

async def delete_weight(update, args):

    date = today_date()

    if args:

        date, label = parse_date(args[0])

        if not date:

            await update.message.reply_text(
                date_error()
            )

            return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM weights
        WHERE DATE(created_at, 'localtime') = ?
        """,
        (format_date(date),)
    )

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    if deleted:

        await update.message.reply_text(
            "🗑️ Weight deleted."
        )

    else:

        await update.message.reply_text(
            "No weight found for that date."
        )


# ==================================================
# SUMMARY
# ==================================================

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):

    date = today_date()
    label = "Today"

    if context.args:

        date, label = parse_date(
            context.args[0]
        )

        if not date:

            await update.message.reply_text(
                date_error()
            )

            return

    date_string = format_date(date)

    conn = get_connection()
    cursor = conn.cursor()

    # Food count and calories
    cursor.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(SUM(calories), 0)
        FROM food
        WHERE DATE(created_at, 'localtime') = ?
        """,
        (date_string,)
    )

    food_count, calories = cursor.fetchone()

    # Weight
    cursor.execute(
        """
        SELECT weight
        FROM weights
        WHERE DATE(created_at, 'localtime') = ?
        """,
        (date_string,)
    )

    weight_row = cursor.fetchone()

    conn.close()

    message = (
        f"📊 {label}\n\n"
        f"🍽 Food entries: {food_count}\n"
        f"🔥 Calories: {calories:.0f} kcal\n"
    )

    if weight_row:

        message += (
            f"⚖️ Weight: "
            f"{weight_row[0]:.1f} kg"
        )

    else:

        message += (
            "⚖️ Weight: Not recorded"
        )

    await update.message.reply_text(message)


# ==================================================
# WEEKLY REPORT
# ==================================================

async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):

    reference_date = today_date()

    if context.args:

        reference_date, _ = parse_date(
            context.args[0]
        )

        if not reference_date:

            await update.message.reply_text(
                date_error()
            )

            return

    # Monday → Sunday
    start_date = (
        reference_date -
        timedelta(days=reference_date.weekday())
    )

    end_date = start_date + timedelta(days=6)

    conn = get_connection()
    cursor = conn.cursor()

    message = (
        "📈 Weekly Report\n"
        f"{start_date.strftime('%d %b')} – "
        f"{end_date.strftime('%d %b %Y')}\n\n"
    )

    weights = []
    calories_list = []
    total_food = 0

    message += "⚖️ Weight\n\n"

    for i in range(7):

        day = start_date + timedelta(days=i)

        cursor.execute(
            """
            SELECT weight
            FROM weights
            WHERE DATE(created_at, 'localtime') = ?
            """,
            (format_date(day),)
        )

        row = cursor.fetchone()

        if row:

            weights.append(
                (day, row[0])
            )

            message += (
                f"{day.strftime('%a')} "
                f"{row[0]:.1f} kg\n"
            )

        else:

            message += (
                f"{day.strftime('%a')} —\n"
            )

    message += "\n━━━━━━━━━━\n\n"

    # Weight statistics
    if weights:

        start_weight = weights[0][1]
        latest_weight = weights[-1][1]

        change = latest_weight - start_weight

        weight_values = [
            value
            for _, value in weights
        ]

        average_weight = (
            sum(weight_values) /
            len(weight_values)
        )

        message += (
            f"Start: {start_weight:.1f} kg\n"
            f"Latest: {latest_weight:.1f} kg\n"
            f"Change: {change:+.1f} kg\n"
            f"Average: {average_weight:.1f} kg\n"
            f"Lowest: {min(weight_values):.1f} kg\n"
            f"Highest: {max(weight_values):.1f} kg\n"
        )

    else:

        message += (
            "No weight data this week.\n"
        )

    message += "\n━━━━━━━━━━\n\n"
    message += "🔥 Calories\n\n"

    for i in range(7):

        day = start_date + timedelta(days=i)

        cursor.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(calories), 0)
            FROM food
            WHERE DATE(created_at, 'localtime') = ?
            """,
            (format_date(day),)
        )

        food_count, calories = cursor.fetchone()

        calories_list.append(calories)
        total_food += food_count

        message += (
            f"{day.strftime('%a')} "
            f"{calories:.0f} kcal\n"
        )

    total_calories = sum(calories_list)

    daily_average = (
        total_calories / 7
    )

    message += (
        f"\n━━━━━━━━━━\n"
        f"Total calories: {total_calories:.0f} kcal\n"
        f"Daily average: {daily_average:.0f} kcal\n"
        f"Food entries: {total_food}"
    )

    conn.close()

    await update.message.reply_text(message)


# ==================================================
# MONTHLY REPORT
# ==================================================

async def monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = today_date()

    if context.args:

        try:

            reference_date = datetime.strptime(
                context.args[0],
                "%Y-%m"
            ).date()

        except ValueError:

            await update.message.reply_text(
                "Usage:\n"
                "/monthly\n"
                "/monthly 2026-09"
            )

            return

    else:

        reference_date = today

    year = reference_date.year
    month = reference_date.month

    # Calculate number of days in month
    if month == 12:

        next_month = datetime(
            year + 1,
            1,
            1
        ).date()

    else:

        next_month = datetime(
            year,
            month + 1,
            1
        ).date()

    start_date = datetime(
        year,
        month,
        1
    ).date()

    end_date = (
        next_month -
        timedelta(days=1)
    )

    conn = get_connection()
    cursor = conn.cursor()

    message = (
        "📅 Monthly Report\n"
        f"{start_date.strftime('%B %Y')}\n\n"
    )

    weights = []
    calorie_values = []
    total_food = 0

    message += "⚖️ Weight\n\n"

    day = start_date

    while day <= end_date:

        cursor.execute(
            """
            SELECT weight
            FROM weights
            WHERE DATE(created_at, 'localtime') = ?
            """,
            (format_date(day),)
        )

        row = cursor.fetchone()

        if row:

            weights.append(
                (day, row[0])
            )

            message += (
                f"{day.strftime('%d %b')} "
                f"{row[0]:.1f} kg\n"
            )

        day += timedelta(days=1)

    if not weights:

        message += "No weight data.\n"

    message += "\n━━━━━━━━━━\n\n"

    # Weight statistics
    if weights:

        weight_values = [
            value
            for _, value in weights
        ]

        change = (
            weight_values[-1] -
            weight_values[0]
        )

        average = (
            sum(weight_values) /
            len(weight_values)
        )

        message += (
            f"Start: {weight_values[0]:.1f} kg\n"
            f"Latest: {weight_values[-1]:.1f} kg\n"
            f"Change: {change:+.1f} kg\n"
            f"Average: {average:.1f} kg\n"
            f"Lowest: {min(weight_values):.1f} kg\n"
            f"Highest: {max(weight_values):.1f} kg\n"
        )

    message += "\n━━━━━━━━━━\n\n"
    message += "🔥 Calories\n\n"

    day = start_date

    while day <= end_date:

        cursor.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(calories), 0)
            FROM food
            WHERE DATE(created_at, 'localtime') = ?
            """,
            (format_date(day),)
        )

        food_count, calories = cursor.fetchone()

        calorie_values.append(calories)
        total_food += food_count

        message += (
            f"{day.strftime('%d %b')} "
            f"{calories:.0f} kcal\n"
        )

        day += timedelta(days=1)

    total_calories = sum(calorie_values)

    days_with_data = len(
        [
            value
            for value in calorie_values
            if value > 0
        ]
    )

    if days_with_data:

        average_calories = (
            total_calories /
            days_with_data
        )

    else:

        average_calories = 0

    message += (
        f"\n━━━━━━━━━━\n"
        f"Total calories: {total_calories:.0f} kcal\n"
        f"Average per logged day: "
        f"{average_calories:.0f} kcal\n"
        f"Food entries: {total_food}"
    )

    conn.close()

    await update.message.reply_text(message)


# ==================================================
# MAIN
# ==================================================

def main():

    if not TOKEN:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN missing from .env"
        )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # Main commands
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("food", food)
    )

    app.add_handler(
        CommandHandler("weight", weight)
    )

    app.add_handler(
        CommandHandler("summary", summary)
    )

    app.add_handler(
        CommandHandler("weekly", weekly)
    )

    app.add_handler(
        CommandHandler("monthly", monthly)
    )

    print("Telegram bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()

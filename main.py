import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests
import schedule
import time
from datetime import datetime, timedelta
import os

# config
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATE_FORMAT= "%Y-%m-%d"

# setup
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
gc = gspread.authorize(creds)

# sheet
SHEET_ID = "1pJL1GixBfPTSlQPORbpJrHTj9S6dDEcDhJ-feVQDyc0"
sheet = gc.open_by_key(SHEET_ID).sheet1

# telegram
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": text})

def get_updates(offset=None):
    params = {"timeout": 100, "offset": offset}
    r = requests.get(f"{API_URL}/getUpdates", params=params)
    return r.json()["result"]

# sheet helpers
def get_dataframe():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_dataframe(df):
    sheet.clear()
    sheet.append_row(list(df.columns))
    sheet.append_rows(df.values.tolist())

# registration
def register_teacher(chat_id, name):
    df = get_dataframe()
    found = False

    for i, row in df.iterrows():
        if row["Teacher Name"].strip().lower() == name.strip().lower():
            df.at[i, "Chat ID"] = chat_id
            found = True
            send_message(chat_id, f"Registered successfully, {name}! You'll receive reminders for your classes.")
            break

        if not found:
            send_message(chat_id, f"Your name '{name}' was not found in the sheet. Please contact the admin.")

        save_dataframe(df)

# reminder
def check_and_send_reminders():
    df = get_dataframe()
    today = datetime.now().date()

    for i, row in df.iterrows():
        if not row["Teaching Date"]:
            continue
        teaching_date = pd.to_datetime(row["Teaching Date"]).date()
        chat_id = row.get("Chat ID")
        if not chat_id:
            continue

        # Get lesson type (with fallback if empty)
        lesson_type = row.get("Lesson Type", "")
        if not lesson_type or pd.isna(lesson_type):
            lesson_info = "a class"
        else:
            lesson_info = lesson_type  # "Teaching Corinthians"

        # 7-day
        if not row["Reminder Sent (7d)"] and teaching_date - today == timedelta(days=7):
            send_message(chat_id, f"Reminder: You have {lesson_info} on {teaching_date} (in 7 days).")
            df.at[i, "Reminder Sent (7d)"] = True

        # 2-day
        if not row["Reminder Sent (2d)"] and teaching_date - today == timedelta(days=2):
            send_message(chat_id, f"Reminder: You have {lesson_info} on {teaching_date} (in 2 days).")
            df.at[i, "Reminder Sent (2d)"] = True

    save_dataframe(df)
    print("Checked reminders at", datetime.now())

def listen_for_new_users():
    print("Listening for new Telegram messages...")
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "").strip()
                if text.lower().startswith("/start"):
                    send_message(chat_id, "Hi! Please reply with your full name.")
                else:
                    register_teacher(chat_id, text)
        time.sleep(5)

# scheduler
def start_scheduler():
    schedule.every().day.at("09:00").do(check_and_send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(60)

# test
def test_reminders_now():
    """Test function - sends reminder regardless of date"""
    df = get_dataframe()
    for i, row in df.iterrows():
        chat_id = row.get("Chat ID")
        if chat_id and row["Teacher Name"] == "Kami Test":  # Replace with your name
            lesson_type = row.get("Lesson Type", "a class")
            teaching_date = row.get("Teaching Date", "TBD")
            send_message(chat_id, f"TEST: You have {lesson_type} on {teaching_date}.")
            print(f"Sent test message to {row['Teacher Name']}")
            
# main
if __name__ == "__main__":
    import threading
    threading.Thread(target=listen_for_new_users, daemon=True).start()
    print("Bot started using Google Sheets...")

    # Test immediately on startup
    time.sleep(5)  # Wait for bot to fully start
    test_reminders_now()
    
    start_scheduler()

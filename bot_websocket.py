import csv
import os
from datetime import datetime
import requests
from dotenv import load_dotenv
from webex_bot.webex_bot import WebexBot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kstrunc@cisco.com")
CSV_FILE = os.getenv("CSV_FILE", "vyber_ponozek.csv")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required (set it in .env).")

try:
    with open(CSV_FILE, "x", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Datum a cas", "Email", "Jmeno", "Vybrane ponozky"])
except FileExistsError:
    pass

class CustomWebexBot(WebexBot):
    def process_incoming_card_action(self, attachment_actions, activity):
        try:
            inputs = attachment_actions.inputs if attachment_actions and hasattr(attachment_actions, "inputs") else {}
            selected_socks = inputs.get("selected_socks", inputs.get("command", "Nezadáno"))

            actor = activity.get("actor", {}) if activity else {}
            person_email = actor.get("emailAddress", "Neznámý")
            person_name = actor.get("displayName", person_email)

            now_str = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            print(f"[{now_str}] 🧦 Volba: {person_name} ({person_email}) -> {selected_socks}")

            # 1. Zápis do CSV
            with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([now_str, person_email, person_name, selected_socks])

            headers = {
                "Authorization": f"Bearer {BOT_TOKEN}",
                "Content-Type": "application/json"
            }

            # 2. Potvrzení zájemci
            user_msg = {
                "toPersonEmail": person_email,
                "markdown": f"Dobrý výběr! 🧦 Zastav se u Květáka pro ponožky. Budou to: **{selected_socks}**."
            }
            requests.post("https://webexapis.com/v1/messages", headers=headers, json=user_msg)

            # 3. Notifikace Květovi
            admin_msg = {
                "toPersonEmail": ADMIN_EMAIL,
                "markdown": f"🧦 **Nový výběr ponožek!**\n\n• **Kdo:** {person_name} ({person_email})\n• **Volba:** **{selected_socks}**\n• **Čas:** {now_str}"
            }
            requests.post("https://webexapis.com/v1/messages", headers=headers, json=admin_msg)

        except Exception as e:
            print(f"Chyba při zpracování akce: {e}")

bot = CustomWebexBot(
    teams_bot_token=BOT_TOKEN,
    approved_users=[],
    bot_name="Ponožkový asistent"
)

if __name__ == "__main__":
    bot.run()
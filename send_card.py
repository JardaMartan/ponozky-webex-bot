import os
from dotenv import load_dotenv

load_dotenv()

from webex_service import WebexService
from sheets_manager import SheetsManager
from card_builder import build_socks_card

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_ROOM = os.getenv("TARGET_ROOM")
TARGET_EMAIL = os.getenv("TARGET_EMAIL")

def main():
    if not BOT_TOKEN:
        print("❌ Chyba: BOT_TOKEN není nastaven v .env")
        return

    webex = WebexService(bot_token=BOT_TOKEN)
    sheets = SheetsManager()
    
    print("📊 Načítám katalog ponožek z Google Sheets...")
    catalog = sheets.get_catalog()
    print(f"✅ Načteno {len(catalog)} položek z katalogu.")

    card = build_socks_card(catalog)

    if TARGET_ROOM:
        print(f"📨 Odesílám Adaptive Card do místnosti (roomId: {TARGET_ROOM})...")
        res = webex.send_message(room_id=TARGET_ROOM, card=card)
    elif TARGET_EMAIL:
        print(f"📨 Odesílám Adaptive Card uživateli {TARGET_EMAIL}...")
        res = webex.send_message(to_person_email=TARGET_EMAIL, card=card)
    else:
        admin_email = os.getenv("ADMIN_EMAIL", "kstrunc@cisco.com")
        print(f"ℹ️ Nebyl specifikován TARGET_ROOM ani TARGET_EMAIL, odesílám adminovi ({admin_email})...")
        res = webex.send_message(to_person_email=admin_email, card=card)

    if res:
        print(f"✅ Karta úspěšně odeslána! (Message ID: {res.get('id')})")
    else:
        print("❌ Chyba při odesílání karty.")

if __name__ == "__main__":
    main()
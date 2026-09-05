import os
import json
from datetime import datetime
import functions_framework
from dotenv import load_dotenv

# Load local .env if present (for local testing with functions-framework)
load_dotenv()

from webex_service import WebexService
from sheets_manager import SheetsManager
from card_builder import build_socks_card, build_order_confirmation_card

# Initialize global services (reused across warm invocations)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "kstrunc@cisco.com")


def get_services():
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    webex = WebexService(bot_token=token)
    sheets = SheetsManager()
    return webex, sheets


@functions_framework.http
def webex_webhook(request):
    """
    Main entry point for Google Cloud Functions (HTTP triggered).
    - GET: Browser setup dashboard & automated webhook configuration.
    - POST: Webex webhook receiver (AttachmentActions and Messages).
    """
    try:
        webex, sheets = get_services()
    except Exception as init_err:
        return (f"Chyba inicializace služeb: {init_err}", 500)

    # =========================================================================
    # 1. HTTP GET: Setup & Webhook Management Dashboard
    # =========================================================================
    if request.method == "GET":
        if request.args.get("action") == "debug_catalog":
            ws = sheets.sheet.worksheet("Nabídka") if sheets.sheet else None
            raw = ws.get_all_values() if ws else []
            return (json.dumps(raw, ensure_ascii=False, indent=2), 200, {"Content-Type": "application/json; charset=utf-8"})
        if request.args.get("action") == "debug_orders":
            ws = sheets.sheet.worksheet("Objednávky") if sheets.sheet else None
            raw = ws.get_all_values() if ws else []
            return (json.dumps(raw, ensure_ascii=False, indent=2), 200, {"Content-Type": "application/json; charset=utf-8"})
        return handle_get_request(request, webex, sheets)

    # =========================================================================
    # 2. HTTP POST: Webex Webhook Event Receiver
    # =========================================================================
    if request.method == "POST":
        return handle_post_webhook(request, webex, sheets)

    return ("Method Not Allowed", 405)


def get_current_function_url(request) -> str:
    """Accurately reconstructs the public URL of the Cloud Function."""
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "https")
    forwarded_host = request.headers.get("X-Forwarded-Host", request.host)
    script_root = request.environ.get("SCRIPT_NAME", "")
    path_info = request.environ.get("PATH_INFO", "")
    full_path = f"{script_root}{path_info}".rstrip("/")

    # If accessed via cloudfunctions.net without function name in path, append function service name
    service_name = os.getenv("K_SERVICE", os.getenv("FUNCTION_TARGET", "webex-socks-bot"))
    if "cloudfunctions.net" in forwarded_host and service_name not in full_path:
        full_path = f"/{service_name}"

    base = f"{forwarded_proto}://{forwarded_host}{full_path}".split("?")[0].rstrip("/")
    return base


def handle_get_request(request, webex: WebexService, sheets: SheetsManager):
    """Handles browser GET requests, automatically registering webhooks and displaying status."""
    # Detect current URL of this Cloud Function
    current_url = get_current_function_url(request)

    # Check query params for actions
    action = request.args.get("action", "setup")
    test_email = request.args.get("test_email")
    test_room = request.args.get("test_room")

    message = ""
    setup_result = None

    if action == "setup" or request.args.get("setup") == "1":
        # Automatically cancel old webhooks and register this URL
        setup_result = webex.setup_webhooks(target_url=current_url)
        message = "✅ Webhooky byly úspěšně nastaveny na tuto URL a všechny předchozí byly zrušeny."

    elif action == "send_test":
        target = test_email or test_room or ADMIN_EMAIL
        catalog = sheets.get_catalog()
        card = build_socks_card(catalog)
        if test_room:
            res = webex.send_message(room_id=test_room, card=card)
        else:
            res = webex.send_message(to_person_email=target, card=card)
        if res:
            message = f"✅ Testovací Adaptive Card byla úspěšně odeslána na: {target}"
        else:
            message = f"❌ Chyba při odesílání testovací karty na: {target}"

    elif action == "seed_catalog":
        overwrite = request.args.get("overwrite") == "1"
        ok = sheets.seed_catalog(overwrite=overwrite)
        if ok:
            message = "✅ Katalog 'Nabídka' byl naplněn výchozími modely ponožek."
        else:
            message = "❌ Katalog se nepodařilo naplnit (Google Sheet není připojen nebo chybí oprávnění)."

    # Fetch current state
    current_webhooks = webex.list_webhooks()
    bot_info = webex.get_bot_info()
    sheet_url = sheets.get_spreadsheet_url()
    catalog_items = sheets.get_catalog()

    # Render HTML Dashboard
    html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🧦 Ponožkový Webex Bot - Serverless Setup</title>
    <style>
        :root {{
            --primary: #0e7fc1;
            --primary-hover: #096397;
            --bg: #f4f7fa;
            --panel: #ffffff;
            --border: #dbe3ec;
            --text: #0a2236;
            --text-secondary: #5b6b7b;
            --success: #2e7d32;
            --success-bg: #e8f5e9;
        }}
        * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
        h1, h2, h3 {{ margin-top: 0; color: var(--text); }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 16px; font-size: 12px; font-weight: 600; text-transform: uppercase; }}
        .badge-success {{ background: var(--success-bg); color: var(--success); }}
        .badge-info {{ background: #e1f5fe; color: #0288d1; }}
        .btn {{ display: inline-block; background: var(--primary); color: white; border: none; padding: 10px 18px; border-radius: 20px; text-decoration: none; font-weight: 600; cursor: pointer; transition: background 0.2s; font-size: 14px; }}
        .btn:hover {{ background: var(--primary-hover); }}
        .btn-outline {{ background: transparent; border: 1px solid var(--primary); color: var(--primary); }}
        .btn-outline:hover {{ background: #e3f2fd; }}
        .alert {{ padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; background: var(--success-bg); color: var(--success); font-weight: 500; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ padding: 10px; border-bottom: 1px solid var(--border); text-align: left; font-size: 14px; }}
        th {{ background: var(--bg); color: var(--text-secondary); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
        .url-box {{ background: var(--bg); border: 1px solid var(--border); padding: 10px 14px; border-radius: 8px; font-family: monospace; word-break: break-all; font-size: 13px; margin: 10px 0; }}
        .form-group {{ margin-bottom: 15px; }}
        .form-group label {{ display: block; font-size: 12px; text-transform: uppercase; color: var(--text-secondary); font-weight: 600; margin-bottom: 6px; }}
        .form-control {{ width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }}
        .row {{ display: flex; gap: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🧦 Ponožkový Webex Bot</h1>
            <p style="color: var(--text-secondary);">Serverless Google Cloud Function + Google Sheets pro výběr firemních ponožek</p>
            <div>
                <span class="badge badge-success">● Cloud Function Aktivní</span>
                <span class="badge badge-info">Bot: {bot_info.get("displayName", "Neznámý")} ({bot_info.get("emails", [""])[0] if bot_info.get("emails") else ""})</span>
            </div>
        </div>

        {f'<div class="alert">{message}</div>' if message else ''}

        <div class="card">
            <h2>⚙️ Automatické nastavení Webhooků</h2>
            <p>Tato Cloud Function automaticky nastavila Webex webhooky na aktuální URL:</p>
            <div class="url-box">{current_url}</div>
            
            <form method="GET">
                <input type="hidden" name="action" value="setup">
                <button type="submit" class="btn">🔄 Přeregistrovat / Aktualizovat webhooky</button>
            </form>

            <h3 style="margin-top: 24px;">Aktivní Webhooky ve Webexu ({len(current_webhooks)}):</h3>
            <table>
                <thead>
                    <tr>
                        <th>Název</th>
                        <th>Zdroj</th>
                        <th>Událost</th>
                        <th>Cílová URL</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f"<tr><td><strong>{w.get('name')}</strong></td><td><code>{w.get('resource')}</code></td><td><code>{w.get('event')}</code></td><td style='font-family:monospace;font-size:12px;'>{w.get('targetUrl')}</td></tr>" for w in current_webhooks]) if current_webhooks else '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary);">Žádné aktivní webhooky. Klikněte na Přeregistrovat webhooky výše.</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>📊 Google Sheets databáze</h2>
            <p>Ponožky, velikosti, obrázky a objednávky jsou spravovány v Google Tabulce:</p>
            {f'<a href="{sheet_url}" target="_blank" class="btn btn-outline" style="margin-bottom:12px;">📂 Otevřít Google Tabulku</a>' if sheet_url else '<p style="color:#d9534f;font-weight:600;">⚠️ Tabulka ještě není propojena nebo Service Account nemá oprávnění k vytváření souborů v Drive.</p>'}

            <form method="GET" style="margin-top:8px;">
                <input type="hidden" name="action" value="seed_catalog">
                <button type="submit" class="btn">🌱 Naplnit katalog výchozími ponožkami (jen prázdné řádky)</button>
            </form>
            
            {f'<div style="background:#eef5fc;border:1px solid #c7e0f4;padding:12px;border-radius:8px;font-size:13px;margin:10px 0;"><strong>💡 Tip pro sdílení:</strong> Vytvořte v Google Drive novou tabulku a nasdílejte ji pro Service Account:<br><code style="font-weight:bold;color:#0e7fc1;">{sheets.service_account_email or "výchozí App Engine / Cloud Functions Service Account"}</code> (s právy Editor). Následně zadejte ID tabulky do proměnné prostředí <code>SPREADSHEET_ID</code>.</div>' if not sheet_url else ''}

            <h3 style="margin-top: 20px;">Aktuální nabídka v katalogu ({len(catalog_items)} položek):</h3>
            <table>
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Velikost</th>
                        <th>Skladem</th>
                        <th>Popis</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f"<tr><td><strong>{item.get('model')}</strong></td><td>{item.get('size')}</td><td>{item.get('stock')} ks</td><td>{item.get('description')}</td></tr>" for item in catalog_items])}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>🚀 Odeslat testovací Adaptive Card</h2>
            <p>Pošlete interaktivní výběrovou kartu konkrétnímu uživateli nebo do prostoru:</p>
            <form method="GET">
                <input type="hidden" name="action" value="send_test">
                <div class="form-group">
                    <label>Email uživatele ve Webexu:</label>
                    <input type="email" name="test_email" class="form-control" value="{ADMIN_EMAIL}" placeholder="user@company.com">
                </div>
                <button type="submit" class="btn">📨 Odeslat výběrovou kartu</button>
            </form>
        </div>
    </div>
</body>
</html>"""

    return (html, 200, {"Content-Type": "text/html; charset=utf-8"})


def handle_post_webhook(request, webex: WebexService, sheets: SheetsManager):
    """Processes incoming Webex Webhooks (Adaptive Card Submits and Messages)."""
    payload = request.get_json(silent=True)
    if not payload:
        return ("Invalid JSON", 400)

    print(f"📩 Webhook event received: resource={payload.get('resource')}, event={payload.get('event')}, data={payload.get('data')}")

    resource = payload.get("resource")
    event = payload.get("event")
    data = payload.get("data", {})
    actor_id = payload.get("actorId")

    # Prevent loop: ignore events generated by the bot itself
    bot_info = webex.get_bot_info()
    bot_id = bot_info.get("id")
    bot_emails = bot_info.get("emails", [])

    if actor_id and actor_id == bot_id:
        return ("Ignored: Bot's own action", 200)

    # =========================================================================
    # A. Adaptive Card Submission (AttachmentActions / Created)
    # =========================================================================
    if resource == "attachmentActions" and event == "created":
        action_id = data.get("id")
        if not action_id:
            return ("Missing action ID", 400)

        # 1. Fetch submitted card inputs
        action_details = webex.get_attachment_action(action_id)
        if not action_details:
            return ("Could not fetch action details", 500)

        inputs = action_details.get("inputs", {})
        selected_raw = inputs.get("selected_sock_item", inputs.get("selected_socks", ""))
        note = inputs.get("order_note", "").strip()

        # Parse model and size
        if "###" in selected_raw:
            model, size = selected_raw.split("###", 1)
        elif "-" in selected_raw:
            parts = selected_raw.split("-", 1)
            model = parts[0].strip()
            size = parts[1].strip()
        else:
            model = selected_raw or "Nezadáno"
            size = "Univerzální"

        # 2. Get Person Details (Who submitted the card)
        person_id = action_details.get("personId") or actor_id
        person_details = webex.get_person_details(person_id) if person_id else {}
        person_email = person_details.get("emails", [""])[0] if person_details.get("emails") else data.get("personEmail", "Neznámý")
        person_name = person_details.get("displayName", person_email)

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        print(f"[{now_str}] 🧦 Objednávka: {person_name} ({person_email}) -> {model} | {size} | Poznámka: {note}")

        # 3. Record order to Google Sheets
        sheets.record_order(
            email=person_email,
            name=person_name,
            model=model,
            size=size,
            note=note,
            status="Nová"
        )

        # 4. Send Confirmation Adaptive Card to User (1:1 direct chat)
        if person_email and person_email != "Neznámý":
            confirm_card = build_order_confirmation_card(model=model, size=size, person_name=person_name, note=note)
            webex.send_message(
                to_person_email=person_email,
                markdown=f"Dobrý výběr! 🧦 Tvoje volba (**{model} - {size}**) byla uložena.",
                card=confirm_card
            )

        # 5. Notify Admin
        admin_email = os.getenv("ADMIN_EMAIL", ADMIN_EMAIL)
        if admin_email:
            admin_msg = (
                f"🧦 **Nový výběr ponožek!**\n\n"
                f"• **Kdo:** {person_name} (`{person_email}`)\n"
                f"• **Model:** **{model}**\n"
                f"• **Velikost:** **{size}**\n"
                f"• **Poznámka:** {note if note else '_bez poznámky_'}\n"
                f"• **Čas:** {now_str}\n\n"
                f"📊 [Otevřít Google Tabulku]({sheets.get_spreadsheet_url()})"
            )
            webex.send_message(to_person_email=admin_email, markdown=admin_msg)

        return ("Order processed", 200)

    # =========================================================================
    # B. Message Received (Messages / Created)
    # =========================================================================
    elif resource == "messages" and event == "created":
        message_id = data.get("id")
        if not message_id:
            return ("Missing message ID", 400)

        # Fetch message text & sender
        msg_details = webex.get_message(message_id)
        if not msg_details:
            return ("Could not fetch message", 500)

        sender_email = msg_details.get("personEmail", "")
        if sender_email in bot_emails:
            # Skip messages sent by the bot itself
            return ("Ignored: Own message", 200)

        room_id = msg_details.get("roomId")
        room_type = msg_details.get("roomType")

        # Prepare dynamic socks card from Google Sheets catalog
        catalog = sheets.get_catalog()
        socks_card = build_socks_card(catalog)

        # Send card to the direct user or the room
        if room_type == "direct":
            webex.send_message(to_person_email=sender_email, card=socks_card)
        else:
            webex.send_message(room_id=room_id, card=socks_card)

        return ("Card sent to user", 200)

    return ("Event received", 200)

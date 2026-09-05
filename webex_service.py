import os
import time
import requests
from typing import Dict, Any, List, Optional

WEBEX_API_URL = "https://webexapis.com/v1"


class WebexService:
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required.")
        self.headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        self._bot_info = None

    def get_bot_info(self) -> Dict[str, Any]:
        """Gets current bot profile (ID, email, displayName)."""
        if self._bot_info:
            return self._bot_info
        try:
            resp = requests.get(f"{WEBEX_API_URL}/people/me", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                self._bot_info = resp.json()
                return self._bot_info
        except Exception as e:
            print(f"Chyba při zjišťování informací o botovi: {e}")
        return {}

    def get_person_details(self, person_id: str) -> Dict[str, Any]:
        """Fetches user details by personId."""
        try:
            resp = requests.get(f"{WEBEX_API_URL}/people/{person_id}", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Chyba při načítání detailu uživatele {person_id}: {e}")
        return {}

    def get_person_by_email(self, email: str) -> Dict[str, Any]:
        """Looks up a person's profile by email address."""
        try:
            resp = requests.get(f"{WEBEX_API_URL}/people", headers=self.headers, params={"email": email}, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    return items[0]
        except Exception as e:
            print(f"Chyba při vyhledávání uživatele podle emailu {email}: {e}")
        return {}

    def get_attachment_action(self, action_id: str, retries: int = 2, backoff_seconds: float = 1.0) -> Dict[str, Any]:
        """Fetches adaptive card submission inputs and details.
        Correct endpoint per Webex docs is /v1/attachment/actions/{id} (note the
        slash) -- NOT /v1/attachmentActions/{id}, which always 404s.
        """
        last_status = None
        last_body = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(f"{WEBEX_API_URL}/attachment/actions/{action_id}", headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                last_status, last_body = resp.status_code, resp.text
                if resp.status_code == 404 and attempt < retries:
                    print(f"⏳ attachmentAction {action_id} zatím není dostupný (pokus {attempt}/{retries}), čekám {backoff_seconds}s...")
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                break
            except Exception as e:
                last_status, last_body = "exception", str(e)
                if attempt < retries:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                break
        print(f"Chyba načtení attachmentAction {action_id} po {retries} pokusech: {last_status} - {last_body}")
        return {}

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Fetches message details by messageId."""
        try:
            resp = requests.get(f"{WEBEX_API_URL}/messages/{message_id}", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Chyba při načítání zprávy {message_id}: {e}")
        return {}

    def send_message(
        self,
        to_person_email: Optional[str] = None,
        room_id: Optional[str] = None,
        to_person_id: Optional[str] = None,
        markdown: Optional[str] = None,
        text: Optional[str] = None,
        card: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Sends a message or adaptive card to a user (1:1) or a space (room)."""
        payload: Dict[str, Any] = {}
        if to_person_email:
            payload["toPersonEmail"] = to_person_email
        elif to_person_id:
            payload["toPersonId"] = to_person_id
        elif room_id:
            payload["roomId"] = room_id
        else:
            raise ValueError("Must provide to_person_email, to_person_id, or room_id.")

        if markdown:
            payload["markdown"] = markdown
        elif text:
            payload["text"] = text

        if card:
            if "markdown" not in payload:
                payload["markdown"] = "🧦 Výběr firemních ponožek (vaše zařízení nepodporuje Adaptive Cards)"
            payload["attachments"] = [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card
                }
            ]

        try:
            resp = requests.post(f"{WEBEX_API_URL}/messages", headers=self.headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                print(f"Chyba při odesílání zprávy: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Výjimka při odesílání zprávy: {e}")
        return None

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """Lists all existing webhooks for this bot."""
        try:
            resp = requests.get(f"{WEBEX_API_URL}/webhooks", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception as e:
            print(f"Chyba při načítání webhooků: {e}")
        return []

    def delete_webhook(self, webhook_id: str) -> bool:
        """Deletes a specific webhook."""
        try:
            resp = requests.delete(f"{WEBEX_API_URL}/webhooks/{webhook_id}", headers=self.headers, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"Chyba při mazání webhooku {webhook_id}: {e}")
            return False

    def delete_all_webhooks(self) -> int:
        """Deletes all existing webhooks for this bot and returns count deleted."""
        webhooks = self.list_webhooks()
        deleted_count = 0
        for wh in webhooks:
            wh_id = wh.get("id")
            if wh_id and self.delete_webhook(wh_id):
                deleted_count += 1
        return deleted_count

    def create_webhook(self, name: str, target_url: str, resource: str, event: str, filter_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Creates a single webhook."""
        payload = {
            "name": name,
            "targetUrl": target_url,
            "resource": resource,
            "event": event
        }
        if filter_str:
            payload["filter"] = filter_str

        try:
            resp = requests.post(f"{WEBEX_API_URL}/webhooks", headers=self.headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                print(f"Chyba při vytváření webhooku '{name}': {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Výjimka při vytváření webhooku '{name}': {e}")
        return None

    def setup_webhooks(self, target_url: str) -> Dict[str, Any]:
        """Cancels all previous webhooks and creates fresh webhooks for card actions and messages."""
        # Clean target URL: strip query parameters or trailing slashes
        clean_url = target_url.split("?")[0].rstrip("/")

        # 1. Cancel all old webhooks
        deleted_count = self.delete_all_webhooks()

        # 2. Create AttachmentActions webhook (for Adaptive Card submits)
        wh_actions = self.create_webhook(
            name="Ponožky Bot - Card Actions",
            target_url=clean_url,
            resource="attachmentActions",
            event="created"
        )

        # 3. Create Messages webhook (for direct / mentioned messages)
        wh_messages = self.create_webhook(
            name="Ponožky Bot - Messages",
            target_url=clean_url,
            resource="messages",
            event="created"
        )

        return {
            "target_url": clean_url,
            "deleted_previous_count": deleted_count,
            "card_actions_webhook": wh_actions,
            "messages_webhook": wh_messages,
            "success": bool(wh_actions and wh_messages)
        }

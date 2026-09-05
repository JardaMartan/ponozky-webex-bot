import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import gspread
from google.oauth2.service_account import Credentials
import google.auth

# Default scopes required for Google Sheets and Google Drive API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CATALOG_HEADERS = ["ID", "Model", "Velikost", "Obrázek URL", "Skladem (ks)", "Popis"]
ORDERS_HEADERS = ["Datum a čas", "Email", "Jméno", "Model", "Velikost", "Poznámka", "Stav"]

DEFAULT_CATALOG = [
    [
        "1",
        "🧦 Klasické dlouhé ponožky",
        "38-42",
        "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=400&auto=format&fit=crop&q=80",
        "25",
        "Pohodlné bavlněné ponožky s firemním logem pro každodenní nošení."
    ],
    [
        "2",
        "🧦 Klasické dlouhé ponožky",
        "43-47",
        "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=400&auto=format&fit=crop&q=80",
        "20",
        "Pohodlné bavlněné ponožky s firemním logem pro každodenní nošení."
    ],
    [
        "3",
        "👟 Nízké kotníkové ponožky",
        "38-42",
        "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=400&auto=format&fit=crop&q=80",
        "30",
        "Lehké a prodyšné kotníkové ponožky ideální do tenisek a pro sport."
    ],
    [
        "4",
        "👟 Nízké kotníkové ponožky",
        "43-47",
        "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=400&auto=format&fit=crop&q=80",
        "15",
        "Lehké a prodyšné kotníkové ponožky ideální do tenisek a pro sport."
    ],
    [
        "5",
        "❄️ Teplé zimní ponožky",
        "39-44",
        "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=400&auto=format&fit=crop&q=80",
        "10",
        "Hřejivé zateplené froté ponožky do chladných dnů."
    ]
]


class SheetsManager:
    def __init__(self, spreadsheet_id: Optional[str] = None):
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")
        self.spreadsheet_name = os.getenv("SPREADSHEET_NAME", "Webex Ponožky - Objednávky a Nabídka")
        self.service_account_email = None
        self.client = self._get_gspread_client()
        self.sheet = None
        if self.client:
            self.sheet = self._get_or_create_spreadsheet()

    def _get_gspread_client(self) -> Optional[gspread.Client]:
        """Authenticates using Service Account JSON file, JSON env var, or ADC (Google Cloud default)."""
        try:
            # 1. From JSON string in environment variable
            creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if creds_json_str:
                info = json.loads(creds_json_str)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                self.service_account_email = info.get("client_email")
                return gspread.authorize(creds)

            # 2. From file path in env or default credentials.json
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            if os.path.exists(creds_file):
                creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
                self.service_account_email = getattr(creds, "service_account_email", None)
                return gspread.authorize(creds)

            # 3. Fallback to Google Cloud Application Default Credentials (when running in Cloud Functions/Cloud Run)
            creds, project_id = google.auth.default(scopes=SCOPES)
            email = getattr(creds, "service_account_email", None)
            if not email or email == "default":
                # Detect standard App Engine / Compute default SA
                project_num = os.getenv("GOOGLE_CLOUD_PROJECT_NUMBER", "")
                if project_num:
                    email = f"{project_num}-compute@developer.gserviceaccount.com"
                elif project_id:
                    email = f"{project_id}@appspot.gserviceaccount.com"
            self.service_account_email = email
            return gspread.authorize(creds)
        except Exception as e:
            print(f"⚠️ Varování: Nelze inicializovat Google Sheets klienta: {e}")
            return None

    def _get_or_create_spreadsheet(self) -> Optional[gspread.Spreadsheet]:
        """Opens existing spreadsheet by ID or Name, or creates a new one."""
        if not self.client:
            return None

        # Try by ID
        if self.spreadsheet_id:
            try:
                sh = self.client.open_by_key(self.spreadsheet_id)
                self._ensure_sheets_structure(sh)
                return sh
            except Exception as e:
                print(f"Chyba při otevírání tabulky podle ID '{self.spreadsheet_id}': {e}")
                print(f"👉 Ujistěte se, že je tabulka nasdílena s editorem: {self.service_account_email or 'Service Accountem z Google Cloud'}")
                return None

        # Try by Name
        try:
            sh = self.client.open(self.spreadsheet_name)
            self.spreadsheet_id = sh.id
            self._ensure_sheets_structure(sh)
            return sh
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet
            try:
                print(f"📄 Vytvářím novou Google Tabulku: '{self.spreadsheet_name}'...")
                sh = self.client.create(self.spreadsheet_name)
                self.spreadsheet_id = sh.id

                # Share with admin if set
                admin_email = os.getenv("ADMIN_EMAIL")
                if admin_email:
                    try:
                        sh.share(admin_email, perm_type="user", role="writer")
                        print(f"✅ Tabulka nasdílena s: {admin_email}")
                    except Exception as share_err:
                        print(f"Upozornění při sdílení s {admin_email}: {share_err}")

                self._ensure_sheets_structure(sh)
                return sh
            except Exception as e:
                print(f"Chyba při vytváření Google tabulky: {e}")
                return None
        except Exception as e:
            print(f"Chyba při hledání tabulky: {e}")
            return None

    def _ensure_sheets_structure(self, sh: gspread.Spreadsheet):
        """Ensures 'Nabídka' and 'Objednávky' worksheets exist with headers."""
        try:
            # 1. Nabídka (Catalog)
            try:
                catalog_ws = sh.worksheet("Nabídka")
            except gspread.WorksheetNotFound:
                catalog_ws = sh.add_worksheet(title="Nabídka", rows=50, cols=10)
                # Remove default 'Sheet1' if it exists and is empty
                try:
                    default_sheet = sh.worksheet("Sheet1")
                    if default_sheet:
                        sh.del_worksheet(default_sheet)
                except Exception:
                    pass

            self._write_header_if_missing(catalog_ws, CATALOG_HEADERS)

            # If there's no data below the header yet, seed with defaults
            if not catalog_ws.row_values(2):
                catalog_ws.update(f"A2:F{len(DEFAULT_CATALOG) + 1}", DEFAULT_CATALOG, value_input_option="USER_ENTERED")

            # 2. Objednávky (Orders)
            try:
                orders_ws = sh.worksheet("Objednávky")
            except gspread.WorksheetNotFound:
                orders_ws = sh.add_worksheet(title="Objednávky", rows=100, cols=10)

            self._write_header_if_missing(orders_ws, ORDERS_HEADERS)
        except Exception as e:
            print(f"Chyba při přípravě struktury tabulky: {e}")

    def _write_header_if_missing(self, ws: gspread.Worksheet, headers: List[str]):
        """Writes the header row at A1 if it doesn't already exactly match, using an
        explicit cell range (not append_row) to avoid gspread's ambiguous row
        detection on sheets that contain phantom blank rows."""
        current_header = ws.row_values(1)
        if [h.strip() for h in current_header] != headers:
            end_col = chr(ord('A') + len(headers) - 1)
            ws.update(f"A1:{end_col}1", [headers], value_input_option="USER_ENTERED")
            ws.format(f"A1:{end_col}1", {"textFormat": {"bold": True}})

    def seed_catalog(self, overwrite: bool = False) -> bool:
        """Force-prefills the 'Nabídka' sheet with the default catalog.
        If overwrite=True, clears all existing data rows and rewrites them.
        Uses explicit cell ranges (not append_row) to avoid gspread's
        ambiguous row detection on sheets with phantom blank rows.
        """
        if not self.sheet:
            print("⚠️ Nelze naplnit katalog: Google Sheet není připojen.")
            return False
        try:
            try:
                catalog_ws = self.sheet.worksheet("Nabídka")
            except gspread.WorksheetNotFound:
                catalog_ws = self.sheet.add_worksheet(title="Nabídka", rows=50, cols=10)

            # Always (re)write a clean header at A1:F1
            self._write_header_if_missing(catalog_ws, CATALOG_HEADERS)

            has_data = bool(catalog_ws.row_values(2))

            if overwrite or not has_data:
                if overwrite:
                    # Clear a generous range below the header first
                    catalog_ws.batch_clear(["A2:F200"])
                catalog_ws.update(f"A2:F{len(DEFAULT_CATALOG) + 1}", DEFAULT_CATALOG, value_input_option="USER_ENTERED")

            return True
        except Exception as e:
            print(f"Chyba při naplňování katalogu: {e}")
            return False

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Returns the list of offered socks from the 'Nabídka' sheet."""
        if not self.sheet:
            # Fallback to default catalog if sheets client is not configured
            return [
                {
                    "id": row[0],
                    "model": row[1],
                    "size": row[2],
                    "image_url": row[3],
                    "stock": int(row[4]) if str(row[4]).isdigit() else 99,
                    "description": row[5] if len(row) > 5 else ""
                }
                for row in DEFAULT_CATALOG
            ]

        try:
            ws = self.sheet.worksheet("Nabídka")
            records = ws.get_all_records()
            items = []
            for r in records:
                stock_val = r.get("Skladem (ks)", r.get("Skladem", 99))
                try:
                    stock_num = int(stock_val)
                except (ValueError, TypeError):
                    stock_num = 99

                items.append({
                    "id": str(r.get("ID", "")),
                    "model": str(r.get("Model", "")),
                    "size": str(r.get("Velikost", "")),
                    "image_url": str(r.get("Obrázek URL", "")),
                    "stock": stock_num,
                    "description": str(r.get("Popis", ""))
                })
            return items
        except Exception as e:
            print(f"Chyba při čtení katalogu z Google Sheet: {e}")
            return []

    def record_order(self, email: str, name: str, model: str, size: str, note: str = "", status: str = "Nová") -> bool:
        """Appends a new order to the 'Objednávky' sheet and optionally decrements stock in 'Nabídka'."""
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        row_data = [now_str, email, name, model, size, note, status]

        if not self.sheet:
            print(f"⚠️ Google Sheets není připojen. Objednávka pro {email} nezapsána do Sheets: {row_data}")
            return False

        try:
            ws = self.sheet.worksheet("Objednávky")
            ws.append_row(row_data)

            # Optional: decrement stock in 'Nabídka' if model and size match
            try:
                catalog_ws = self.sheet.worksheet("Nabídka")
                records = catalog_ws.get_all_records()
                for idx, item in enumerate(records, start=2): # start=2 because row 1 is header
                    if item.get("Model") == model and str(item.get("Velikost")) == str(size):
                        curr_stock = int(item.get("Skladem (ks)", item.get("Skladem", 0)))
                        if curr_stock > 0:
                            catalog_ws.update_cell(idx, 5, curr_stock - 1)
                        break
            except Exception as dec_err:
                print(f"Upozornění při odečtu skladu: {dec_err}")

            return True
        except Exception as e:
            print(f"Chyba při zápisu objednávky do Google Sheet: {e}")
            return False

    def get_spreadsheet_url(self) -> str:
        """Returns the public or shareable URL of the Google Sheet."""
        if self.sheet:
            return self.sheet.url
        if self.spreadsheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
        return ""

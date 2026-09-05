# 🧦 Webex Ponožkový Bot (Serverless + Google Sheets)

Serverless Webex Bot běžící na **Google Cloud Functions (2nd gen)** využívající **Webhooks**, **Google Sheets API** a **Adaptive Cards 1.2**.

---

## 🌟 Hlavní funkce a architektura

1. **Serverless (Google Cloud Functions)**:
   - Žádné trvale běžící procesy ani WebSockety – bot spí a probudí se pouze při příchozím webhooku.
2. **Automatické nastavení Webhooků na 1 kliknutí v prohlížeči**:
   - Stačí v prohlížeči otevřít URL nasazené Cloud Function.
   - Endpoint automaticky zjistí svou veřejnou URL, smaže všechny staré/neplatné webhooky bota a zaregistruje nové pro události `attachmentActions` (odeslání karty) a `messages` (příchozí zpráva).
   - Zobrazí přehledný webový dashboard s diagnostikou, odkazem do Google Tabulky a tlačítkem pro odeslání testovací karty.
3. **Google Sheets jako databáze**:
   - **List `Nabídka`**: Spravuje nabízené modely, velikosti, URL obrázků, skladovou zásobu a popisky. Změny v tabulce se okamžitě projeví na kartách!
   - **List `Objednávky`**: Automaticky zapisuje datum, email, jméno, vybraný model, velikost, poznámku a stav.
   - **Odečet ze skladu**: Při každé objednávce se automaticky sníží počet kusů v listu `Nabídka`.
4. **Interaktivní Adaptive Cards**:
   - Dynamicky generovaná karta s náhledovými obrázky modelů, výběrem velikosti a volitelnou poznámkou.
   - Po odeslání dostane uživatel 1:1 potvrzovací kartu a administrátor dostane notifikaci s odkazem do tabulky.

---

## 📂 Struktura projektu

- [main.py](main.py) – Hlavní HTTP handler pro Cloud Function (GET: Dashboard & Auto-setup, POST: Webhooks).
- [sheets_manager.py](sheets_manager.py) – Správa Google Sheets (načítání katalogu, zápis objednávek, inicializace tabulky).
- [webex_service.py](webex_service.py) – Komunikace s Webex REST API (zprávy, attachmentActions, správa webhooků).
- [card_builder.py](card_builder.py) – Dynamický generátor Webex Adaptive Cards.
- [send_card.py](send_card.py) – Pomocný skript pro manuální odeslání karty do prostoru či uživateli.
- [requirements.txt](requirements.txt) – Python závislosti.
- [.env.example](.env.example) – Vzor konfigurace prostředí.

---

## 🚀 Nasazení na Google Cloud Platform (GCP)

### Krok 1: Povolení potřebných API na GCP
V Google Cloud Console povolte:
- **Cloud Functions API**
- **Cloud Run Admin API**
- **Cloud Build API**
- **Google Sheets API**
- **Google Drive API**

Nebo v terminálu:
```bash
gcloud services enable cloudfunctions.googleapis.com cloudbuild.googleapis.com run.googleapis.com sheets.googleapis.com drive.googleapis.com
```

### Krok 2: Oprávnění pro Google Sheets (Service Account)
1. V Cloud Console přejděte na **IAM & Admin > Service Accounts**.
2. Vytvořte Service Account (např. `webex-socks-bot@<project-id>.iam.gserviceaccount.com`).
3. Vygenerujte JSON klíč a uložte jako `credentials.json` (pro lokální běh), nebo povolte výchozímu účtu Cloud Functions přístup k tabulce.
4. **Důležité:** V Google Tabulce klikněte na **Sdílet** a přidejte email tohoto Service Accountu jako **Editor**.

### Krok 3: Nasazení Cloud Function
Z kořenového adresáře projektu spusťte:

```bash
gcloud functions deploy webex-socks-bot \
  --gen2 \
  --runtime=python311 \
  --region=europe-west1 \
  --source=. \
  --entry-point=webex_webhook \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars BOT_TOKEN="VÁŠ_WEBEX_BOT_TOKEN",ADMIN_EMAIL="admin@example.com"
```

---

## 🔗 Automatické nastavení Webhooků (One-Click)

Po úspěšném nasazení vám Google Cloud vypíše URL funkce (např. `https://europe-west1-project.cloudfunctions.net/webex-socks-bot`).

1. **Otevřete tuto URL ve vašem webovém prohlížeči.**
2. Funkce provede:
   - Smazání všech dřívějších webhooků bota.
   - Vytvoření nových webhooků pro `attachmentActions` a `messages` směřujících přesně na tuto Cloud Function.
   - Vytvoření/inicializaci Google Tabulky.
3. V prohlížeči se zobrazí dashboard potvrzující stav a odkaz do Google Tabulky.

---

## 💻 Lokální testování (Functions Framework)

1. Vytvořte a aktivujte virtuální prostředí:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Zkopírujte `.env.example` do `.env` a doplňte `BOT_TOKEN`.
3. Spusťte lokální server:
   ```bash
   functions-framework --target=webex_webhook --port=8080 --debug
   ```
4. Pro vystavení na internet pro Webex webhooky použijte např. ngrok:
   ```bash
   ngrok http 8080
   ```
5. Otevřete ngrok URL v prohlížeči pro automatickou registraci webhooků.

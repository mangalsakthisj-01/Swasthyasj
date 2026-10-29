# SwasthyaGrid — Civic Intelligence & Community Health-Risk Triage

A flat-file Streamlit application designed for direct upload to a GitHub repository. The entrypoint is `app.py`; the backend services are `backend_services.py` and `backend_triage.py` at the repository root, so Python does not depend on a nested `backend/` folder.

## Newly implemented in this build

- **Admin-published hotspot advisories:** create an official advisory by area/ward, category, severity, description, precautions, source/verification note, optional map coordinates, and expiry date/time.
- **Citizen notifications:** publishing a hotspot inserts persistent in-app notifications for active Citizen accounts whose jurisdiction matches the advisory; choosing `All Areas` sends notifications to all active Citizens. Closing an advisory generates a citizen update. Case assignment/status changes also create in-app messages.
- **Hotspot lifecycle:** map pins, active/expired/closed states, Admin closure with a required reason, audit events, and closure update notifications.
- **Field Officer investigation report:** structured date/time, inspection outcome, location confirmation, observed conditions, findings/root cause, officer-assessed severity, estimated people affected, environmental conditions, immediate safety actions, action taken, materials, department referral, pending work, recommendations, citizen contact/feedback, follow-up date, conclusion, extra notes, and photo/audio/video/document attachments.
- **Downloads:** Citizens can download their own case report as PDF and personal case history as CSV. Field Officers can download their saved investigation reports as PDFs and an investigation index CSV. Admins and permitted Representatives can review/download investigation PDFs and indexes. Operations and oversight complaint reports remain downloadable as CSV.
- **Interactive maps:** complaint pins from submitted coordinates, area-level automatic hotspot signals, and coordinates for Admin-published hotspot advisories.
- **Optional AI-assisted triage/image review:** Gemini-assisted evaluation is used only when configured and consent is given in the relevant submission flow; rules-based triage remains available without an API key.
- **Role-based views:** Citizen, Field Officer, Admin, and Representative.

## Deploy to Streamlit Community Cloud

1. Download and extract `SwasthyaGrid_Advanced_GitHub_Streamlit.zip`.
2. Create a new, empty GitHub repository (recommended: `swasthyagrid-streamlit`).
3. From the extracted folder, upload these files directly to the repository root: `app.py`, `backend_services.py`, `backend_triage.py`, `requirements.txt`, `README.md`, `DEPLOY_NOW.txt`, `IMPLEMENTED_FEATURES.md`, and optionally `FEATURE_CATALOG.md` and `.gitignore`. Do **not** upload the ZIP as one file.
4. Commit the upload to branch `main`.
5. Open <https://share.streamlit.io/> → **Create app**.
6. Select your repository, branch `main`, and main file path `app.py`; click **Deploy**.
7. For optional AI image/text analysis, set `GEMINI_API_KEY` in the app's Streamlit Secrets UI. Do not put a real key in GitHub.

The first deployment installs packages from `requirements.txt`; a quick launch is the goal, not a guarantee if GitHub upload or package installation is slow.

## Local run

Requires Python 3.11 or newer and internet access for the first dependency installation:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Open <http://localhost:8501>.

## Demo accounts

| Role | User ID | Password |
|---|---|---|
| Admin | `admin` | `Admin@12345` |
| Field Officer | `officer` | `Officer@12345` |
| Representative | `representative` | `Rep@123456` |
| Citizen | `citizen` | `Citizen@12345` |

These are public demonstration credentials. Do not use them for real citizen records. Change demo access and configure a durable database before any public or sensitive deployment.

## Hotspot workflow

1. Sign in as Admin.
2. Open **Hotspot & citizen alerts**.
3. Complete the title, category, severity, affected ward/scope, public-facing explanation, precautions, source, expiry, and optional coordinates.
4. Click **Publish hotspot & notify citizens**. A persistent alert is stored, matching Citizen accounts receive in-app notifications, and the active advisory appears in the map/alert view.
5. After review, select the active advisory, enter a closure reason, and close it. Matching citizens receive a closure-update notification.

The current notifications are **in-app**. SMS, WhatsApp, email and browser push are not active integrations in this ZIP.

## Field investigation workflow

1. Sign in as Field Officer and open an assigned or jurisdiction-visible case.
2. Fill the structured **Field investigation report** after site inspection. Required fields: inspection date/time, outcome, observed conditions, investigation findings, action taken, and recommendations.
3. Add site evidence if needed and save the report.
4. Download the generated investigation PDF from the saved reports section. Update the case status separately; resolving a complaint still requires an operational action note.

## Important limits and safety

- Automatic hotspot clusters and Admin-published alerts are operational signals/advisories, not proof of a disease outbreak or a medical diagnosis.
- AI image/text review is advisory. It does not conclusively verify that a report is true/false; uncertain reports remain reviewable.
- Exact case coordinates can be sensitive. Use approximate public hotspot coordinates, not a citizen's home pin.
- SQLite data under `data/` may not persist across Streamlit cloud restarts/redeployments. Use a durable managed database and private media storage before real deployment.
- Current citizen notifications are stored in-app and are created for active Citizen accounts matching the selected area at publish time. Area-filtered active advisories also remain visible in their dashboard until closed/expired.
- This is a deployable prototype, not a certified government, medical, emergency dispatch, or security-audited service.

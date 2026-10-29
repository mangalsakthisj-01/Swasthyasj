# SwasthyaGrid — Implemented Workflows in This Package

## Admin hotspot publishing

- Publish official hotspot advisories scoped to one ward or `All Areas`.
- Required title, category, severity, area, public detail, source/review note, and expiry.
- Optional approximate coordinates for map display.
- Persistent record with an active/closed lifecycle.
- In-app notifications sent to matching active Citizen accounts when published.
- Closing with a reason creates closure update notifications for the same area audience.
- Admin table, expiry, status, source and closure reason.
- Audit events for publishing and closing.

## Citizen alert and report experience

- In-app notification inbox with unread/read state.
- Active official hotspot advisories, precautions, source, issue time, expiry and optional map location.
- Area-filtered advisories remain visible while active.
- Download own complaint history as CSV and individual case report as PDF.
- Case assignment and status change notices are added to the citizen inbox.

## Field Officer investigation report

- Inspection date and time, outcome, location confirmation, observed conditions, findings/root cause, assessed severity, estimated number affected, environmental conditions, immediate safety actions, action taken, materials/equipment, referral department, blockers, recommendations, citizen contact/feedback, follow-up checkbox/date, conclusion and notes.
- Required fields are validated by the backend.
- Optional photo, audio, video and PDF evidence is attached to the case with an investigation report reference note.
- Backend checks role and case assignment/jurisdiction before saving.
- Each saved report receives its own ID and timestamp and can be downloaded as PDF.
- Officer can download a CSV report index.

## Oversight

- Admin can review and download the investigation index and individual report PDFs.
- Representatives can see/download investigation reports only when the relevant case is in their permitted oversight view.
- CSV downloads for case/oversight reports.
- PDF report text is escaped before rendering to avoid interpreting user-supplied text as report markup.

## Known deployment constraints

- Notifications are in-app only. External SMS, WhatsApp, email, and browser push are not connected.
- SQLite is appropriate for a demo but not a substitute for a durable managed production database on an ephemeral host.
- Maps display report/hotspot pins when coordinates exist. Use approximate public area coordinates; do not publish private home locations.
- AI assessments and clusters are advisory only and do not confirm an outbreak or prove a complaint's truth.

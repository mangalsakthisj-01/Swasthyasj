"""Flat-file backend services for SwasthyaGrid (SQLite, auth, workflow, audit)."""
from __future__ import annotations
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend_triage import assess_complaint

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SWASTHYAGRID_DATA_DIR", str(APP_DIR / "data")))
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "swasthyagrid.db")))
ROLES = ("Citizen", "Field Officer", "Admin", "Representative")
STATUSES = ("Submitted", "Triaged", "Assigned", "In Progress", "Escalated", "Resolved", "Reopened")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return f"pbkdf2_sha256$260000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac(algo.split("_")[-1], password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False


def audit(con: sqlite3.Connection, actor: str, action: str, complaint_id: str | None = None, detail: str = "") -> None:
    con.execute("INSERT INTO audit_logs(actor,action,complaint_id,detail,created_at) VALUES(?,?,?,?,?)", (actor, action, complaint_id, detail[:1000], now()))


def init_db() -> None:
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL, full_name TEXT NOT NULL,
          jurisdiction TEXT NOT NULL DEFAULT 'General', active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
          id TEXT PRIMARY KEY, citizen_username TEXT NOT NULL, complainant_name TEXT NOT NULL,
          title TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
          area TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL, severity TEXT NOT NULL,
          risk_level TEXT NOT NULL, priority_score INTEGER NOT NULL,
          ai_validation TEXT NOT NULL, ai_confidence INTEGER NOT NULL, ai_reason TEXT NOT NULL,
          triage_provider TEXT NOT NULL, review_required INTEGER NOT NULL,
          critical_override INTEGER NOT NULL, status TEXT NOT NULL,
          assigned_officer TEXT NOT NULL DEFAULT '', representative TEXT NOT NULL DEFAULT '',
          action_taken TEXT NOT NULL DEFAULT '', remarks TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS evidence (
          id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
          uploaded_by TEXT NOT NULL, filename TEXT NOT NULL, mime_type TEXT NOT NULL,
          data BLOB NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
          action TEXT NOT NULL, complaint_id TEXT, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS hotspot_alerts (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL,
          area TEXT NOT NULL, description TEXT NOT NULL, precautions TEXT NOT NULL DEFAULT '',
          latitude REAL, longitude REAL, source TEXT NOT NULL DEFAULT 'Admin reviewed',
          status TEXT NOT NULL DEFAULT 'Active', public_notice INTEGER NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
          closed_at TEXT NOT NULL DEFAULT '', closure_reason TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_username TEXT NOT NULL,
          kind TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL,
          hotspot_id TEXT, complaint_id TEXT, created_at TEXT NOT NULL, read_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS investigation_reports (
          id TEXT PRIMARY KEY, complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
          officer_username TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hotspot_area_status ON hotspot_alerts(area,status);
        CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_username,read_at);
        CREATE INDEX IF NOT EXISTS idx_investigation_case ON investigation_reports(complaint_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_complaints_area_category ON complaints(area,category);
        CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
        CREATE INDEX IF NOT EXISTS idx_evidence_complaint ON evidence(complaint_id);
        """)
        # Backward-compatible schema migration for repositories deployed before map support.
        existing_columns = {row[1] for row in con.execute("PRAGMA table_info(complaints)").fetchall()}
        if "latitude" not in existing_columns:
            con.execute("ALTER TABLE complaints ADD COLUMN latitude REAL")
        if "longitude" not in existing_columns:
            con.execute("ALTER TABLE complaints ADD COLUMN longitude REAL")
        users = con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        allow_demo = os.getenv("ALLOW_DEMO_LOGINS", "true").lower() == "true"
        bootstrap_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if users == 0 and allow_demo:
            seed = [
                ("admin", "Admin@12345", "Admin", "System Administrator", "All Areas"),
                ("officer", "Officer@12345", "Field Officer", "Sample Field Officer", "Central Ward"),
                ("representative", "Rep@123456", "Representative", "Sample Representative", "Central Ward"),
                ("citizen", "Citizen@12345", "Citizen", "Sample Citizen", "Central Ward"),
            ]
            for username, password, role, name, area in seed:
                con.execute("INSERT INTO users(username,password_hash,role,full_name,jurisdiction,created_at) VALUES(?,?,?,?,?,?)",
                            (username, hash_password(password), role, name, area, now()))
        elif users == 0 and bootstrap_password:
            con.execute("INSERT INTO users(username,password_hash,role,full_name,jurisdiction,created_at) VALUES(?,?,?,?,?,?)",
                        ("admin", hash_password(bootstrap_password), "Admin", "System Administrator", "All Areas", now()))


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    init_db()
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE username=? AND active=1", (username.strip(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            with connect() as con2:
                audit(con2, username.strip() or "unknown", "LOGIN_FAILED", detail="Invalid credentials")
            return None
        audit(con, row["username"], "LOGIN_SUCCESS")
        return dict(row)


def list_users(role: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with connect() as con:
        if role:
            rows = con.execute("SELECT id,username,role,full_name,jurisdiction,active,created_at FROM users WHERE role=? ORDER BY full_name", (role,)).fetchall()
        else:
            rows = con.execute("SELECT id,username,role,full_name,jurisdiction,active,created_at FROM users ORDER BY role,full_name").fetchall()
        return [dict(x) for x in rows]


def create_user(actor: str, username: str, password: str, role: str, full_name: str, jurisdiction: str) -> tuple[bool, str]:
    init_db()
    username = username.strip()
    if len(username) < 3 or not username.replace("_", "").replace("-", "").isalnum():
        return False, "User ID must be at least 3 characters using letters, digits, _ or -"
    if len(password) < 10:
        return False, "Password must have at least 10 characters"
    if role not in ROLES:
        return False, "Invalid role"
    try:
        with connect() as con:
            con.execute("INSERT INTO users(username,password_hash,role,full_name,jurisdiction,created_at) VALUES(?,?,?,?,?,?)",
                        (username, hash_password(password), role, full_name.strip() or username, jurisdiction.strip() or "General", now()))
            audit(con, actor, "USER_CREATED", detail=f"username={username}; role={role}")
        return True, f"Created account {username}"
    except sqlite3.IntegrityError:
        return False, "That User ID already exists"


def get_user(username: str) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT id,username,role,full_name,jurisdiction,active,created_at FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None


def submit_complaint(citizen: dict[str, Any], title: str, category: str, description: str, area: str,
                     address: str, severity: str, files: list[dict[str, Any]] | None = None,
                     allow_external_ai: bool = False, api_key: str | None = None,
                     latitude: float | None = None, longitude: float | None = None) -> dict[str, Any]:
    init_db()
    files = files or []
    image_file = next((f for f in files if f.get("mime_type", "").startswith("image/")), None)
    triage = assess_complaint(category, description, severity,
                              image_file.get("data") if image_file else None,
                              image_file.get("mime_type") if image_file else None,
                              allow_external_ai, api_key)
    complaint_id = "SG-" + uuid.uuid4().hex[:8].upper()
    status = "Escalated" if triage["critical_override"] else "Triaged"
    officer = ""
    rep = ""
    if status == "Escalated":
        officers = list_users("Field Officer")
        reps = list_users("Representative")
        officer = next((u["username"] for u in officers if u["jurisdiction"] in {area, "All Areas", "General"}), officers[0]["username"] if officers else "")
        rep = next((u["username"] for u in reps if u["jurisdiction"] in {area, "All Areas", "General"}), reps[0]["username"] if reps else "")
    with connect() as con:
        con.execute("""INSERT INTO complaints(id,citizen_username,complainant_name,title,category,description,area,address,latitude,longitude,severity,risk_level,priority_score,ai_validation,ai_confidence,ai_reason,triage_provider,review_required,critical_override,status,assigned_officer,representative,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (complaint_id, citizen["username"], citizen.get("full_name", citizen["username"]), title.strip(), category, description.strip(), area.strip() or "General", address.strip(), latitude, longitude, triage["severity"], triage["risk_level"], triage["priority_score"], triage["ai_validation"], triage["ai_confidence"], triage["ai_reason"], triage["triage_provider"], int(triage["review_required"]), int(triage["critical_override"]), status, officer, rep, now(), now()))
        for f in files:
            data = f.get("data", b"")
            if not data:
                continue
            con.execute("INSERT INTO evidence(complaint_id,uploaded_by,filename,mime_type,data,note,created_at) VALUES(?,?,?,?,?,?,?)",
                        (complaint_id, citizen["username"], Path(f.get("filename", "evidence.bin")).name[:200], f.get("mime_type", "application/octet-stream")[:120], data, "Citizen-submitted evidence", now()))
        audit(con, citizen["username"], "COMPLAINT_SUBMITTED", complaint_id, f"category={category}; risk={triage['risk_level']}; score={triage['priority_score']}")
        if triage["critical_override"]:
            audit(con, "system", "CRITICAL_BYPASS", complaint_id, "Routed to escalated queue")
        result = con.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        return dict(result)


def _visible_clause(user: dict[str, Any]) -> tuple[str, list[Any]]:
    role, username, area = user["role"], user["username"], user.get("jurisdiction", "General")
    if role == "Citizen":
        return "citizen_username=?", [username]
    if role == "Field Officer":
        return "(assigned_officer=? OR (assigned_officer='' AND area IN (?, 'General')))", [username, area]
    if role == "Representative":
        return "(representative=? OR (representative='' AND area IN (?, 'General')) OR status='Escalated')", [username, area]
    return "1=1", []


def list_complaints(user: dict[str, Any], limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    clause, params = _visible_clause(user)
    with connect() as con:
        rows = con.execute(f"SELECT c.*, (SELECT COUNT(*) FROM evidence e WHERE e.complaint_id=c.id) AS evidence_count FROM complaints c WHERE {clause} ORDER BY c.critical_override DESC,c.priority_score DESC,c.created_at DESC LIMIT ?", [*params, limit]).fetchall()
        return [dict(r) for r in rows]


def get_complaint(complaint_id: str) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        return dict(row) if row else None


def assign_complaint(actor: str, complaint_id: str, officer: str, representative: str) -> tuple[bool, str]:
    with connect() as con:
        row = con.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        if not row:
            return False, "Complaint not found"
        if officer and not con.execute("SELECT 1 FROM users WHERE username=? AND role='Field Officer' AND active=1", (officer,)).fetchone():
            return False, "Choose a valid active Field Officer"
        if representative and not con.execute("SELECT 1 FROM users WHERE username=? AND role='Representative' AND active=1", (representative,)).fetchone():
            return False, "Choose a valid active Representative"
        status = "Assigned" if row["status"] in {"Submitted", "Triaged", "Reopened"} and officer else row["status"]
        con.execute("UPDATE complaints SET assigned_officer=?,representative=?,status=?,updated_at=? WHERE id=?", (officer, representative, status, now(), complaint_id))
        audit(con, actor, "COMPLAINT_ASSIGNED", complaint_id, f"officer={officer}; representative={representative}")
        con.execute("INSERT INTO notifications(recipient_username,kind,title,message,complaint_id,created_at) VALUES(?,?,?,?,?,?)",
                    (row["citizen_username"], "CASE_ASSIGNED", "A field team has been assigned", f"Your report {complaint_id} has been routed to the responsible field team. Follow the case status in SwasthyaGrid.", complaint_id, now()))
    return True, "Assignment saved; citizen notified in-app"


def update_complaint(actor: dict[str, Any], complaint_id: str, status: str, action_taken: str, remarks: str,
                     files: list[dict[str, Any]] | None = None) -> tuple[bool, str]:
    if status not in STATUSES:
        return False, "Invalid status"
    with connect() as con:
        row = con.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
        if not row:
            return False, "Complaint not found"
        role = actor["role"]
        if role == "Citizen" and row["citizen_username"] != actor["username"]:
            return False, "You can update only your own reports"
        if role == "Field Officer" and row["assigned_officer"] not in ("", actor["username"]):
            return False, "This complaint is assigned to another officer"
        if role == "Representative" and row["representative"] not in ("", actor["username"]) and row["status"] != "Escalated":
            return False, "This complaint is not assigned to your oversight queue"
        if status == "Resolved" and not action_taken.strip():
            return False, "Record the action taken before marking a case resolved"
        if role == "Citizen" and status not in {"Reopened"}:
            return False, "Citizens may reopen resolved cases, not change operational statuses"
        resolved_at = now() if status == "Resolved" else None
        con.execute("UPDATE complaints SET status=?,action_taken=?,remarks=?,updated_at=?,resolved_at=? WHERE id=?",
                    (status, action_taken.strip(), remarks.strip(), now(), resolved_at, complaint_id))
        for f in (files or []):
            data = f.get("data", b"")
            if data:
                con.execute("INSERT INTO evidence(complaint_id,uploaded_by,filename,mime_type,data,note,created_at) VALUES(?,?,?,?,?,?,?)",
                            (complaint_id, actor["username"], Path(f.get("filename", "evidence.bin")).name[:200], f.get("mime_type", "application/octet-stream")[:120], data, "Field update evidence", now()))
        audit(con, actor["username"], "COMPLAINT_STATUS_UPDATED", complaint_id, f"status={status}; action={action_taken[:150]}")
        if role != "Citizen":
            note = f"Your report {complaint_id} status is now '{status}'."
            if remarks.strip():
                note += f" Update: {remarks.strip()[:800]}"
            con.execute("INSERT INTO notifications(recipient_username,kind,title,message,complaint_id,created_at) VALUES(?,?,?,?,?,?)",
                        (row["citizen_username"], "CASE_STATUS", f"Complaint status updated: {status}", note, complaint_id, now()))
        else:
            recipients = con.execute("SELECT username FROM users WHERE active=1 AND role IN ('Admin','Field Officer') AND (jurisdiction=? OR jurisdiction='All Areas' OR role='Admin')", (row["area"],)).fetchall()
            for recipient in recipients:
                con.execute("INSERT INTO notifications(recipient_username,kind,title,message,complaint_id,created_at) VALUES(?,?,?,?,?,?)",
                            (recipient["username"], "CASE_REOPENED", "Citizen reopened a complaint", f"Case {complaint_id} was reopened by the citizen. Please review the reason and next action.", complaint_id, now()))
    return True, "Complaint updated; citizen notified in-app" if role != "Citizen" else "Complaint reopened; responsible team notified in-app"


def add_evidence(actor: str, complaint_id: str, filename: str, mime_type: str, data: bytes, note: str = "") -> None:
    with connect() as con:
        con.execute("INSERT INTO evidence(complaint_id,uploaded_by,filename,mime_type,data,note,created_at) VALUES(?,?,?,?,?,?,?)",
                    (complaint_id, actor, Path(filename).name[:200], mime_type[:120], data, note[:500], now()))
        audit(con, actor, "EVIDENCE_UPLOADED", complaint_id, filename)


def evidence_for(complaint_id: str) -> list[dict[str, Any]]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT id,complaint_id,uploaded_by,filename,mime_type,data,note,created_at FROM evidence WHERE complaint_id=? ORDER BY created_at", (complaint_id,)).fetchall()]


def summary(user: dict[str, Any]) -> dict[str, int]:
    cases = list_complaints(user)
    return {
        "total": len(cases), "open": sum(c["status"] not in {"Resolved"} for c in cases),
        "critical": sum(bool(c["critical_override"]) for c in cases),
        "escalated": sum(c["status"] == "Escalated" for c in cases),
        "resolved": sum(c["status"] == "Resolved" for c in cases),
        "review": sum(bool(c["review_required"]) for c in cases),
    }


def hotspots(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate location/category signals for staff; a hotspot is an investigation signal, not an outbreak claim."""
    cases = list_complaints(user)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in cases:
        buckets.setdefault((c["area"], c["category"]), []).append(c)
    result = []
    for (area, category), items in buckets.items():
        if len(items) >= 3:
            coords = [(float(x["latitude"]), float(x["longitude"])) for x in items if x.get("latitude") is not None and x.get("longitude") is not None]
            result.append({"Area": area, "Category": category, "Reports": len(items), "Open": sum(x["status"] != "Resolved" for x in items), "Critical": sum(bool(x["critical_override"]) for x in items), "Latitude": round(sum(x[0] for x in coords)/len(coords), 5) if coords else None, "Longitude": round(sum(x[1] for x in coords)/len(coords), 5) if coords else None, "Verification": "Unverified signal", "Window": "All recorded reports"})
    return sorted(result, key=lambda x: (x["Critical"], x["Reports"]), reverse=True)


def public_hotspots() -> list[dict[str, Any]]:
    """Aggregate-only public hotspot signals; suppress exact coordinates and small groups."""
    init_db()
    with connect() as con:
        rows = con.execute(
            "SELECT area AS Area, category AS Category, COUNT(*) AS Reports, "
            "SUM(CASE WHEN status != 'Resolved' THEN 1 ELSE 0 END) AS Open, "
            "SUM(critical_override) AS Critical, AVG(latitude) AS Latitude, AVG(longitude) AS Longitude "
            "FROM complaints GROUP BY area, category HAVING COUNT(*) >= 3 "
            "ORDER BY SUM(critical_override) DESC, COUNT(*) DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Round area-level centroid to reduce location precision in the public view.
            d["Latitude"] = round(d["Latitude"], 2) if d["Latitude"] is not None else None
            d["Longitude"] = round(d["Longitude"], 2) if d["Longitude"] is not None else None
            d["Verification"] = "Unverified signal"
            d["Window"] = "All recorded reports"
            result.append(d)
        return result


def audit_events(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT id,actor,action,complaint_id,detail,created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


def export_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b"No complaints to export\n"
    # Avoid exporting unnecessary personal name fields by default.
    fields = ["id", "title", "category", "area", "severity", "risk_level", "priority_score", "status", "assigned_officer", "representative", "action_taken", "remarks", "created_at", "updated_at"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def evidence_for_user(user: dict[str, Any], complaint_id: str) -> list[dict[str, Any]]:
    c = get_complaint(complaint_id)
    if not c:
        return []
    if user["role"] == "Citizen" and c["citizen_username"] != user["username"]:
        return []
    allowed = list_complaints(user)
    if not any(x["id"] == complaint_id for x in allowed):
        return []
    return evidence_for(complaint_id)


# ---------------------------------------------------------------------------
# Admin-published hotspot advisories, citizen in-app notifications, and field
# investigation reports. These services use the same durable SQLite store.
# ---------------------------------------------------------------------------

def create_hotspot_alert(actor: dict[str, Any], title: str, category: str, severity: str,
                         area: str, description: str, precautions: str = "",
                         latitude: float | None = None, longitude: float | None = None,
                         source: str = "Admin reviewed", expires_at: str | None = None,
                         public_notice: bool = True) -> tuple[bool, str, str]:
    """Create an official in-app hotspot alert and notify citizens in its scope."""
    init_db()
    if actor.get("role") != "Admin":
        return False, "Only an Admin can publish an official hotspot advisory", ""
    title, area = title.strip(), area.strip()
    if len(title) < 4 or len(description.strip()) < 8 or not area:
        return False, "Enter a clear title, area, and description", ""
    try:
        if not expires_at:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
        else:
            # Accept a valid ISO timestamp from the UI, normalised for comparison.
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            expires_at = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return False, "Expiry must be a valid date and time", ""
    if (latitude is None) != (longitude is None):
        return False, "Provide both latitude and longitude, or leave both blank", ""
    if latitude is not None and not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
        return False, "Map coordinates are outside valid ranges", ""
    alert_id = "HS-" + uuid.uuid4().hex[:8].upper()
    created_at = now()
    scope_all = area.lower() in {"all areas", "all wards", "public"}
    with connect() as con:
        con.execute("""INSERT INTO hotspot_alerts
          (id,title,category,severity,area,description,precautions,latitude,longitude,source,status,public_notice,created_by,created_at,expires_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (alert_id, title, category, severity, area, description.strip(), precautions.strip(),
           latitude, longitude, source.strip() or "Admin reviewed", "Active", int(public_notice),
           actor.get("username", "admin"), created_at, expires_at))
        if public_notice:
            if scope_all:
                recipients = con.execute("SELECT username FROM users WHERE active=1 AND role='Citizen'").fetchall()
            else:
                recipients = con.execute("SELECT username FROM users WHERE active=1 AND role='Citizen' AND (jurisdiction=? OR jurisdiction='All Areas')", (area,)).fetchall()
            message = f"{severity} {category} advisory for {area}. {description.strip()}"
            if precautions.strip():
                message += f" Precautions: {precautions.strip()}"
            for row in recipients:
                con.execute("INSERT INTO notifications(recipient_username,kind,title,message,hotspot_id,created_at) VALUES(?,?,?,?,?,?)",
                            (row["username"], "HOTSPOT_PUBLISHED", title, message[:3000], alert_id, created_at))
        audit(con, actor.get("username", "admin"), "HOTSPOT_PUBLISHED", detail=f"id={alert_id}; area={area}; severity={severity}; public={int(public_notice)}")
    return True, f"Hotspot {alert_id} published and citizen in-app notifications queued", alert_id


def list_hotspot_alerts(user: dict[str, Any], include_closed: bool = False, limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    role = user.get("role")
    username = user.get("username", "")
    area = user.get("jurisdiction", "General")
    clauses, params = [], []
    if not include_closed:
        clauses.append("status='Active'")
        clauses.append("(expires_at='' OR expires_at > ?)")
        params.append(now())
    if role == "Citizen":
        clauses.append("public_notice=1")
        if area not in ("All Areas", "General", ""):
            clauses.append("(area=? OR lower(area) IN ('all areas','all wards','public'))")
            params.append(area)
        else:
            clauses.append("lower(area) IN ('all areas','all wards','public')")
    elif role in ("Field Officer", "Representative"):
        if area not in ("All Areas", "General", ""):
            clauses.append("(area=? OR lower(area) IN ('all areas','all wards','public'))")
            params.append(area)
    elif role != "Admin":
        return []
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as con:
        rows = con.execute(f"SELECT * FROM hotspot_alerts{where} ORDER BY CASE severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, created_at DESC LIMIT ?", [*params, limit]).fetchall()
        return [dict(r) for r in rows]


def close_hotspot_alert(actor: dict[str, Any], alert_id: str, reason: str) -> tuple[bool, str]:
    if actor.get("role") != "Admin":
        return False, "Only an Admin can close an official hotspot alert"
    if len(reason.strip()) < 5:
        return False, "Add a closure reason for the audit trail"
    with connect() as con:
        row = con.execute("SELECT * FROM hotspot_alerts WHERE id=?", (alert_id,)).fetchone()
        if not row:
            return False, "Hotspot alert not found"
        if row["status"] != "Active":
            return False, "This hotspot is already closed"
        con.execute("UPDATE hotspot_alerts SET status='Closed',closed_at=?,closure_reason=? WHERE id=?", (now(), reason.strip(), alert_id))
        if row["public_notice"]:
            scope_all = row["area"].lower() in {"all areas", "all wards", "public"}
            if scope_all:
                recipients = con.execute("SELECT username FROM users WHERE active=1 AND role='Citizen'").fetchall()
            else:
                recipients = con.execute("SELECT username FROM users WHERE active=1 AND role='Citizen' AND (jurisdiction=? OR jurisdiction='All Areas')", (row["area"],)).fetchall()
            for recipient in recipients:
                con.execute("INSERT INTO notifications(recipient_username,kind,title,message,hotspot_id,created_at) VALUES(?,?,?,?,?,?)",
                            (recipient["username"], "HOTSPOT_CLOSED", f"Advisory update: {row['title']}", f"The advisory for {row['area']} has been closed by Admin. Reason: {reason.strip()}", alert_id, now()))
        audit(con, actor.get("username", "admin"), "HOTSPOT_CLOSED", detail=f"id={alert_id}; reason={reason[:300]}")
    return True, "Hotspot closed and in-app update notifications queued"


def list_notifications(user: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with connect() as con:
        rows = con.execute("SELECT id,kind,title,message,hotspot_id,complaint_id,created_at,read_at FROM notifications WHERE recipient_username=? ORDER BY id DESC LIMIT ?", (user.get("username", ""), limit)).fetchall()
        return [dict(r) for r in rows]


def mark_notification_read(user: dict[str, Any], notification_id: int) -> tuple[bool, str]:
    with connect() as con:
        cur = con.execute("UPDATE notifications SET read_at=? WHERE id=? AND recipient_username=?", (now(), int(notification_id), user.get("username", "")))
        if cur.rowcount:
            audit(con, user.get("username", "unknown"), "NOTIFICATION_READ", detail=f"notification_id={notification_id}")
            return True, "Notification marked as read"
    return False, "Notification not found"


def save_investigation_report(actor: dict[str, Any], complaint_id: str, fields: dict[str, Any]) -> tuple[bool, str, str]:
    """Save a structured field officer report; permission checks run in the backend."""
    if actor.get("role") != "Field Officer":
        return False, "Only a Field Officer can submit an investigation report", ""
    case = get_complaint(complaint_id)
    if not case:
        return False, "Complaint not found", ""
    if case.get("assigned_officer") not in ("", actor.get("username")):
        return False, "This complaint is assigned to another Field Officer", ""
    if case.get("assigned_officer") == "" and case.get("area") not in (actor.get("jurisdiction", "General"), "General", "All Areas") and actor.get("jurisdiction") not in ("General", "All Areas"):
        return False, "This complaint is outside your jurisdiction", ""
    required = ["visit_datetime", "inspection_result", "observed_conditions", "investigation_findings", "action_taken", "recommendations"]
    missing = [key for key in required if not str(fields.get(key, "")).strip()]
    if missing:
        return False, "Required fields missing: " + ", ".join(missing), ""
    report_id = "IR-" + uuid.uuid4().hex[:10].upper()
    timestamp = now()
    encoded = json.dumps(fields, ensure_ascii=False, default=str)
    with connect() as con:
        con.execute("INSERT INTO investigation_reports(id,complaint_id,officer_username,report_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (report_id, complaint_id, actor["username"], encoded, timestamp, timestamp))
        audit(con, actor["username"], "INVESTIGATION_REPORT_CREATED", complaint_id, f"report_id={report_id}; result={str(fields.get('inspection_result',''))[:100]}")
        # Keep a human-readable latest summary in the complaint timeline as well.
        con.execute("UPDATE complaints SET remarks=?,updated_at=? WHERE id=?",
                    (f"Investigation {report_id}: {str(fields.get('inspection_result',''))}. {str(fields.get('recommendations',''))}"[:2000], timestamp, complaint_id))
    return True, f"Investigation report {report_id} saved", report_id


def list_investigation_reports(user: dict[str, Any], complaint_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    role = user.get("role")
    visible = {c["id"] for c in list_complaints(user, limit=1000)}
    if role == "Citizen":
        # Citizens may download their case summary, but field investigation notes are staff records.
        return []
    sql = "SELECT ir.*, c.title AS complaint_title, c.area AS complaint_area, c.category AS complaint_category, c.status AS complaint_status FROM investigation_reports ir JOIN complaints c ON c.id=ir.complaint_id"
    where, params = [], []
    if complaint_id:
        where.append("ir.complaint_id=?")
        params.append(complaint_id)
    if role != "Admin":
        if not visible:
            return []
        marks = ",".join("?" for _ in visible)
        where.append(f"ir.complaint_id IN ({marks})")
        params.extend(sorted(visible))
        if role == "Field Officer":
            where.append("ir.officer_username=?")
            params.append(user.get("username", ""))
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ir.created_at DESC LIMIT ?"
    params.append(limit)
    with connect() as con:
        rows = con.execute(sql, params).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["fields"] = json.loads(d.pop("report_json"))
        except Exception:
            d["fields"] = {}
        result.append(d)
    return result


def get_investigation_report(user: dict[str, Any], report_id: str) -> dict[str, Any] | None:
    rows = list_investigation_reports(user, limit=1000)
    return next((r for r in rows if r["id"] == report_id), None)

from __future__ import annotations
import os
import io
from html import escape
from datetime import datetime, date, time, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from backend_services import (
    ROLES, STATUSES, add_evidence, assign_complaint, audit_events, authenticate,
    create_user, evidence_for_user, export_csv, get_complaint, get_user,
    hotspots, public_hotspots, init_db, list_complaints, list_users, submit_complaint, summary,
    update_complaint, create_hotspot_alert, list_hotspot_alerts, close_hotspot_alert,
    list_notifications, mark_notification_read, save_investigation_report,
    list_investigation_reports,
)

st.set_page_config(page_title="SwasthyaGrid | Civic Intelligence", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --sg-ink:#142d3b; --sg-teal:#0d9488; --sg-blue:#2563eb; }
.block-container {padding-top:1.35rem; padding-bottom:2.5rem; max-width:1500px;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#effaf8 0%,#f4f7fb 100%);}
[data-testid="stMetric"] {background:linear-gradient(135deg,#ffffff,#f4faf9); border:1px solid #dcebe8; padding:15px 16px; border-radius:16px; box-shadow:0 3px 14px rgba(20,45,59,.04);}
[data-testid="stMetricLabel"] {color:#496574;}
div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {background:linear-gradient(90deg,#0f766e,#2563eb); border:0; border-radius:10px; font-weight:650;}
[data-testid="stTabs"] button {font-weight:650;}
.sg-hero {padding:1.25rem 1.4rem; border-radius:18px; color:#fff; background:linear-gradient(120deg,#123044 0%,#0f766e 58%,#2563eb 100%); margin-bottom:1rem;}
.sg-hero h2 {color:white; margin:0;}
.sg-muted {color:#607987; font-size:.92rem;}
</style>
""", unsafe_allow_html=True)

CATEGORY_OPTIONS = ["Water & Drainage", "Road & Transport", "Waste & Sanitation", "Public Health", "Electricity & Lighting", "Other Civic Issue"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]


def secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "")
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def notice(message: str, kind: str = "success") -> None:
    st.session_state["sg_notice"] = (message, kind)


def show_notice() -> None:
    item = st.session_state.pop("sg_notice", None)
    if item:
        message, kind = item
        getattr(st, kind if kind in {"success", "info", "warning", "error"} else "info")(message)


def uploaded_files(items: list[Any] | None) -> list[dict[str, Any]]:
    result = []
    total_bytes = 0
    max_mb = int(secret("MAX_UPLOAD_MB", "10") or "10")
    for item in items or []:
        data = item.getvalue()
        total_bytes += len(data)
        if len(data) > max_mb * 1024 * 1024:
            st.warning(f"{item.name} exceeds the {max_mb} MB per-file limit and was skipped.")
            continue
        result.append({"filename": item.name, "mime_type": item.type or "application/octet-stream", "data": data})
    if total_bytes > max_mb * 1024 * 1024 * 3:
        st.warning("Large total upload selected. Consider attaching only the most useful evidence.")
    return result


def table_for_cases(cases: list[dict[str, Any]]) -> pd.DataFrame:
    columns = ["id", "title", "category", "area", "severity", "risk_level", "priority_score", "status", "assigned_officer", "representative", "evidence_count", "created_at"]
    rows = [{k: c.get(k, "") for k in columns} for c in cases]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df = df.rename(columns={"id": "Case ID", "title": "Title", "category": "Category", "area": "Area", "severity": "Severity", "risk_level": "Risk", "priority_score": "Priority", "status": "Status", "assigned_officer": "Field Officer", "representative": "Representative", "evidence_count": "Evidence", "created_at": "Reported At"})
    return df


def build_pdf(title: str, sections: list[tuple[str, dict[str, Any] | list[tuple[str, Any]]]]) -> bytes:
    """Build a compact printable report PDF with escaped, user-supplied text."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm,
                            topMargin=16*mm, bottomMargin=16*mm, title=title)
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("SGTitle", parent=styles["Title"], textColor=colors.HexColor("#123044"), alignment=TA_CENTER, spaceAfter=8)
    section_style = ParagraphStyle("SGSection", parent=styles["Heading2"], textColor=colors.HexColor("#0f766e"), spaceBefore=9, spaceAfter=5)
    value_style = ParagraphStyle("SGValue", parent=styles["BodyText"], fontSize=8.8, leading=12, wordWrap="CJK")
    label_style = ParagraphStyle("SGLabel", parent=styles["BodyText"], fontSize=8.8, leading=12, textColor=colors.HexColor("#334155"))
    story = [Paragraph(escape(title), heading), Paragraph(f"Generated by SwasthyaGrid · {escape(datetime.now().strftime('%d %b %Y, %H:%M'))}", styles["Italic"]), Spacer(1, 5)]
    for heading_text, values in sections:
        story.append(Paragraph(escape(str(heading_text)), section_style))
        pairs = list(values.items()) if isinstance(values, dict) else list(values)
        table_rows = []
        for key, value in pairs:
            text = str(value if value not in (None, "") else "—")
            text = escape(text).replace("\n", "<br/>")
            table_rows.append([Paragraph(escape(str(key)), label_style), Paragraph(text, value_style)])
        if table_rows:
            table = Table(table_rows, colWidths=[43*mm, 130*mm], repeatRows=0, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f1f5f9")),
                ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#d9e3e8")),
                ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
                ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ]))
            story.append(table)
            story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Notice: AI assessments and hotspot signals are advisory. Field observations reflect the reporting officer's recorded findings and do not replace qualified medical, engineering, or emergency assessment.", styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()


def case_report_pdf(case: dict[str, Any]) -> bytes:
    sections = [
        ("Case information", {
            "Case ID": case.get("id"), "Title": case.get("title"), "Category": case.get("category"),
            "Area / Ward": case.get("area"), "Landmark": case.get("address"), "Reported at": case.get("created_at"),
            "Severity": case.get("severity"), "Current status": case.get("status"), "Priority score": case.get("priority_score"),
            "Assigned Field Officer": case.get("assigned_officer") or "Not assigned", "Representative": case.get("representative") or "Not assigned",
        }),
        ("Citizen-submitted description", {"Description": case.get("description"), "Triage note": case.get("ai_reason"),
         "Latest action taken": case.get("action_taken"), "Latest remarks": case.get("remarks")}),
    ]
    if case.get("latitude") is not None and case.get("longitude") is not None:
        sections.append(("Location pin", {"Latitude": case.get("latitude"), "Longitude": case.get("longitude")}))
    return build_pdf(f"SwasthyaGrid Citizen Case Report · {case.get('id','')}", sections)


def investigation_report_pdf(report: dict[str, Any]) -> bytes:
    fields = report.get("fields", {})
    label_map = {
        "visit_datetime": "Inspection date and time", "inspection_result": "Inspection outcome",
        "location_confirmed": "Location confirmed", "observed_conditions": "Observed conditions",
        "investigation_findings": "Investigation findings / likely cause", "severity_assessed": "Officer-assessed severity",
        "people_affected": "Estimated people potentially affected", "environment_conditions": "Environmental conditions",
        "immediate_safety_actions": "Immediate safety actions", "action_taken": "Action taken during visit",
        "materials_used": "Materials / equipment used", "department_referral": "Department / agency referral",
        "pending_work": "Pending work / blockers", "recommendations": "Recommendations",
        "citizen_contacted": "Citizen contacted", "citizen_feedback": "Citizen feedback / contact notes",
        "follow_up_required": "Follow-up required", "follow_up_date": "Follow-up date",
        "conclusion": "Officer conclusion", "additional_notes": "Additional notes",
    }
    values = {label_map.get(k, k.replace("_", " ").title()): v for k, v in fields.items()}
    sections = [
        ("Report metadata", {"Investigation Report ID": report.get("id"), "Case ID": report.get("complaint_id"),
          "Case title": report.get("complaint_title"), "Area / Ward": report.get("complaint_area"),
          "Officer User ID": report.get("officer_username"), "Saved at": report.get("created_at"),
          "Inspection result": fields.get("inspection_result", "")}),
        ("Field investigation details", values),
    ]
    return build_pdf(f"Field Investigation Report · {report.get('complaint_id','')}", sections)


def render_notifications(user: dict[str, Any]) -> None:
    notifications = list_notifications(user)
    alerts = list_hotspot_alerts(user)
    unread = sum(not n.get("read_at") for n in notifications)
    st.subheader(f"🔔 Local notifications · {unread} unread")
    if not notifications and not alerts:
        st.info("No official in-app alerts for your area yet. If an Admin publishes a hotspot advisory for your ward, it will appear here.")
    for alert in alerts:
        with st.container(border=True):
            badge = "🚨" if alert.get("severity") == "Critical" else "⚠️" if alert.get("severity") == "High" else "📣"
            st.markdown(f"### {badge} {alert.get('title')} · {alert.get('severity')}")
            st.write(f"**Area:** {alert.get('area')} · **Category:** {alert.get('category')} · **Published:** {alert.get('created_at')}")
            st.write(alert.get("description", ""))
            if alert.get("precautions"):
                st.warning("Precautions: " + alert["precautions"])
            st.caption(f"Source: {alert.get('source') or 'Admin reviewed'} · Expires: {alert.get('expires_at')} · Advisory, not a diagnosis or a confirmed outbreak.")
    if notifications:
        with st.expander("Notification inbox", expanded=bool(unread)):
            for n in notifications:
                st.markdown(f"**{'🟢' if not n.get('read_at') else '⚪'} {n.get('title')}**")
                st.write(n.get("message", ""))
                st.caption(f"{n.get('kind')} · {n.get('created_at')}")
                if not n.get("read_at") and st.button("Mark as read", key=f"read_notification_{n['id']}"):
                    mark_notification_read(user, int(n["id"]))
                    st.rerun()
                st.divider()


def render_staff_inbox(user: dict[str, Any]) -> None:
    notifications = list_notifications(user)
    unread = sum(not n.get("read_at") for n in notifications)
    with st.expander(f"🔔 Operations inbox · {unread} unread", expanded=False):
        if not notifications:
            st.caption("No new operational notifications.")
        for item in notifications[:15]:
            st.markdown(f"**{'🟢' if not item.get('read_at') else '⚪'} {item.get('title')}**")
            st.write(item.get("message", ""))
            st.caption(f"{item.get('kind')} · {item.get('created_at')}")
            if not item.get("read_at") and st.button("Mark read", key=f"staff_read_{item['id']}"):
                mark_notification_read(user, int(item["id"]))
                st.rerun()
            st.divider()


def render_metrics(user: dict[str, Any]) -> None:
    s = summary(user)
    cols = st.columns(5)
    for col, label, key in zip(cols, ["Total reports", "Open cases", "Critical alerts", "Escalated", "Resolved"], ["total", "open", "critical", "escalated", "resolved"]):
        col.metric(label, s[key])


def render_hotspots(user: dict[str, Any]) -> None:
    st.subheader("🗺️ CivicPulse · Hotspot intelligence")
    rows = public_hotspots() if user["role"] == "Citizen" else hotspots(user)
    if rows:
        st.caption("Automatically detected clusters are investigation signals, not confirmed outbreaks. They use repeated reports and must be reviewed.")
        df = pd.DataFrame(rows)
        map_df = df.dropna(subset=["Latitude", "Longitude"]).rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
        if not map_df.empty:
            st.map(map_df[["latitude", "longitude"]], color="#0d9488", size=180)
        st.dataframe(df.drop(columns=["Latitude", "Longitude"], errors="ignore"), use_container_width=True, hide_index=True)
    else:
        st.info("No automatic repeated-report signal in this area yet.")

    alerts = list_hotspot_alerts(user)
    st.markdown("#### 📣 Admin-published hotspot advisories")
    if alerts:
        st.caption("These advisories were explicitly published by an Admin. Citizens in the target area receive an in-app notification. External SMS/push delivery is not configured in this prototype.")
        alert_df = pd.DataFrame(alerts)
        coords = alert_df.dropna(subset=["latitude", "longitude"]).rename(columns={"latitude": "latitude", "longitude": "longitude"})
        if not coords.empty:
            st.map(coords[["latitude", "longitude"]], color="#dc2626", size=240)
        show_cols = [c for c in ["id", "title", "category", "severity", "area", "source", "created_at", "expires_at"] if c in alert_df.columns]
        st.dataframe(alert_df[show_cols], use_container_width=True, hide_index=True)
        if user["role"] == "Citizen":
            for alert in alerts[:5]:
                with st.container(border=True):
                    st.markdown(f"**{'🚨' if alert.get('severity') == 'Critical' else '⚠️'} {alert.get('title')}** · {alert.get('severity')}")
                    st.write(f"{alert.get('area')} · {alert.get('category')}")
                    st.write(alert.get("description", ""))
                    if alert.get("precautions"):
                        st.warning("Precautions: " + alert["precautions"])
                    st.caption(f"Source: {alert.get('source')} · Expires: {alert.get('expires_at')}")
    else:
        st.info("No active Admin-published advisory for this account's area.")

def render_incident_map(user: dict[str, Any], cases: list[dict[str, Any]]) -> None:
    st.subheader("🌍 CivicTwin · Incident map")
    st.caption("Explore reports with submitted coordinates. Citizen view is limited to their own cases and approximate public hotspot signals; staff views follow role/jurisdiction permissions.")
    if cases:
        df = pd.DataFrame(cases)
        if "latitude" in df.columns and "longitude" in df.columns:
            df = df.dropna(subset=["latitude", "longitude"])
            if not df.empty:
                df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
                df = df.dropna(subset=["latitude", "longitude"])
                st.map(df[["latitude", "longitude"]], color="#2563eb", size=100)
                st.dataframe(df[["id", "title", "category", "area", "severity", "status", "latitude", "longitude"]], use_container_width=True, hide_index=True)
            else:
                st.info("No report pins yet. Citizens can add coordinates when submitting a report.")
        else:
            st.info("No map coordinates are stored yet. New reports can include a map pin.")
    else:
        st.info("No reports are available in this view yet.")
    render_hotspots(user)

def render_evidence(user: dict[str, Any], complaint_id: str) -> None:
    items = evidence_for_user(user, complaint_id)
    if not items:
        st.caption("No evidence available for this case, or you do not have permission to view it.")
        return
    st.markdown("**Attached evidence**")
    for item in items:
        left, right = st.columns([3, 1])
        left.write(f"📎 **{item['filename']}** · {item['mime_type']} · uploaded by {item['uploaded_by']}")
        right.download_button("Download", data=item["data"], file_name=item["filename"], mime=item["mime_type"], key=f"dl_{item['id']}")
        if item["note"]:
            st.caption(item["note"])


def render_login() -> None:
    st.markdown("<div class='sg-hero'><h2>🌐 SwasthyaGrid</h2><div style='opacity:.92;margin-top:6px'>Civic intelligence · Community health-risk signals · Verified action</div></div>", unsafe_allow_html=True)
    st.subheader("Civic Intelligence & Health-Risk Triage")
    st.write("Report local issues, coordinate field action, flag emerging hotspots, and track resolution with an auditable workflow.")
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown("### Sign in")
        with st.form("login_form"):
            username = st.text_input("User ID", placeholder="Enter your User ID")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state["sg_user"] = {k: user[k] for k in ("id", "username", "role", "full_name", "jurisdiction", "active")}
                notice(f"Welcome, {user['full_name']}!")
                st.rerun()
            else:
                st.error("Login failed. Check the User ID and password.")
        st.caption("For a quick demo, use one of the sample accounts shown to the right. Change demo credentials before any public or real-data use.")
    with right:
        st.markdown("### Demo access")
        st.warning("These are public demo credentials. Do not use them for production data.")
        accounts = [
            ("Admin", "admin", "Admin@12345"),
            ("Field Officer", "officer", "Officer@12345"),
            ("Representative", "representative", "Rep@123456"),
            ("Citizen", "citizen", "Citizen@12345"),
        ]
        for role, uid, pwd in accounts:
            st.markdown(f"**{role}** · User ID: `{uid}` · Password: `{pwd}`")
    st.divider()
    st.caption("Prototype notice: risk scores are advisory, not medical diagnoses or proof that a report is true. Suspected emergencies require real-world emergency services and human follow-up.")


def render_citizen(user: dict[str, Any]) -> None:
    st.title("👋 Welcome, Citizen")
    st.write("Raise a civic issue, attach evidence, and follow its progress.")
    render_metrics(user)
    with st.expander("🔔 Alerts and notification inbox", expanded=True):
        render_notifications(user)
    with st.expander("🗺️ Explore your reports and local hotspot signals", expanded=True):
        render_incident_map(user, list_complaints(user))
    st.divider()
    st.subheader("📝 Raise a complaint")
    api_key = secret("GEMINI_API_KEY")
    with st.form("complaint_form", clear_on_submit=True):
        title = st.text_input("Short title", placeholder="e.g. Drain overflowing near bus stop", max_chars=140)
        c1, c2 = st.columns(2)
        category = c1.selectbox("Issue category", CATEGORY_OPTIONS)
        severity = c2.selectbox("How urgent does it seem?", SEVERITIES, index=1)
        area = st.text_input("Ward / area", value=user.get("jurisdiction", "Central Ward"), max_chars=100)
        address = st.text_input("Landmark or address (optional)", max_chars=240)
        with st.expander("📍 Add a map pin (recommended)"):
            st.caption("Enter coordinates from your map app. Leave both at 0 if you do not want to share a precise pin. The app does not automatically access your GPS.")
            lat_col, lon_col = st.columns(2)
            latitude_input = lat_col.number_input("Latitude", min_value=-90.0, max_value=90.0, value=0.0, format="%.6f")
            longitude_input = lon_col.number_input("Longitude", min_value=-180.0, max_value=180.0, value=0.0, format="%.6f")
        description = st.text_area("Describe the issue", placeholder="What happened, where, and when? Avoid including sensitive personal information.", height=120, max_chars=4000)
        evidence = st.file_uploader("Attach photos, audio or video", type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "mp4", "mov", "pdf"], accept_multiple_files=True)
        consent = False
        if api_key:
            consent = st.checkbox("Optional AI image/text analysis: I consent to sending report text and one attached image to Gemini for an advisory category/urgency review. The report is kept even if AI is uncertain or unavailable.")
        else:
            st.caption("AI image analysis is currently in rules-only mode. To enable Gemini vision, add GEMINI_API_KEY in Streamlit app Settings → Secrets. Do not put API keys in GitHub.")
        submit = st.form_submit_button("Submit complaint", type="primary", use_container_width=True)
    if submit:
        if not title.strip() or len(description.strip()) < 8:
            st.error("Please enter a title and a more detailed description.")
        else:
            files = uploaded_files(evidence)
            latitude = latitude_input if latitude_input != 0.0 or longitude_input != 0.0 else None
            longitude = longitude_input if latitude is not None else None
            result = submit_complaint(user, title, category, description, area, address, severity, files,
                                      allow_external_ai=bool(consent and api_key), api_key=api_key if consent else None,
                                      latitude=latitude, longitude=longitude)
            notice(f"Complaint {result['id']} submitted. Current status: {result['status']}.")
            st.rerun()
    cases = list_complaints(user)
    st.divider()
    st.subheader("📍 My complaints and tracking")
    st.dataframe(table_for_cases(cases), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download my complaint history (CSV)", data=export_csv(cases), file_name=f"my_swasthyagrid_cases_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", key="citizen_history_csv")
    if cases:
        case_id = st.selectbox("View a complaint", [c["id"] for c in cases], key="citizen_case_select")
        case = get_complaint(case_id)
        if case:
            with st.container(border=True):
                st.markdown(f"### {case['id']} · {case['title']}")
                st.write(f"**Status:** {case['status']} · **Risk:** {case['risk_level']} · **Priority score:** {case['priority_score']}")
                st.write(case["description"])
                st.info(f"Triage: {case['ai_validation']} — {case['ai_reason']}")
                if case.get("action_taken"):
                    st.write(f"**Action taken:** {case['action_taken']}")
                if case.get("remarks"):
                    st.write(f"**Latest remarks:** {case['remarks']}")
                render_evidence(user, case_id)
                st.download_button("⬇️ Download my case report (PDF)", data=case_report_pdf(case), file_name=f"SwasthyaGrid_{case_id}.pdf", mime="application/pdf", key=f"citizen_pdf_{case_id}")
            if case["status"] == "Resolved":
                if st.button("Reopen this complaint", key=f"reopen_{case_id}"):
                    ok, msg = update_complaint(user, case_id, "Reopened", case.get("action_taken", ""), "Citizen requested review of the resolution.")
                    notice(msg, "success" if ok else "error")
                    st.rerun()


def render_officer(user: dict[str, Any]) -> None:
    st.title("🧰 Field Officer Console")
    st.write(f"Jurisdiction: **{user.get('jurisdiction', 'General')}** · Investigate, document findings, upload evidence, and track follow-up work.")
    render_metrics(user)
    cases = list_complaints(user)
    with st.expander("🗺️ Field map & hotspot signals", expanded=True):
        render_incident_map(user, cases)
    st.subheader("Assigned and area complaints")
    st.dataframe(table_for_cases(cases), use_container_width=True, hide_index=True)
    reports_all = list_investigation_reports(user)
    if reports_all:
        rpt_table = pd.DataFrame([{"Report ID": r["id"], "Case ID": r["complaint_id"], "Case title": r.get("complaint_title"), "Area": r.get("complaint_area"), "Inspection result": r.get("fields", {}).get("inspection_result"), "Saved at": r.get("created_at")} for r in reports_all])
        with st.expander("📚 My submitted investigation reports", expanded=False):
            st.dataframe(rpt_table, use_container_width=True, hide_index=True)
            st.download_button("Download investigation index (CSV)", data=rpt_table.to_csv(index=False).encode("utf-8-sig"), file_name="field_investigation_index.csv", mime="text/csv")
    if not cases:
        st.info("No reports are currently assigned to you or visible in your area.")
        return
    case_id = st.selectbox("Choose a complaint", [c["id"] for c in cases], key="officer_case_select")
    case = get_complaint(case_id)
    if not case:
        return
    with st.container(border=True):
        st.markdown(f"### {case['id']} · {case['title']}")
        st.write(f"**Category:** {case['category']} · **Area:** {case['area']} · **Risk:** {case['risk_level']} · **Status:** {case['status']}")
        st.write(case["description"])
        st.info(f"Triage note: {case['ai_validation']} — {case['ai_reason']}")
        render_evidence(user, case_id)

    st.subheader("📝 Structured field investigation report")
    st.caption("Complete this report after a site visit. Required fields are marked with *. Keep observations factual; do not infer a person's health status from an image or complaint.")
    with st.form(f"investigation_form_{case_id}", clear_on_submit=True):
        d1, d2 = st.columns(2)
        visit_date = d1.date_input("Inspection date *", value=date.today(), key=f"visit_date_{case_id}")
        visit_time = d2.time_input("Inspection time *", value=datetime.now().time().replace(second=0, microsecond=0), key=f"visit_time_{case_id}")
        c1, c2, c3 = st.columns(3)
        inspection_result = c1.selectbox("Inspection outcome *", ["Verified", "Partially verified", "Not observed at visit", "Unable to verify", "Critical hazard observed"], key=f"inspection_result_{case_id}")
        location_confirmed = c2.selectbox("Location confirmed?", ["Yes", "Partly", "No", "Not applicable"], key=f"location_confirmed_{case_id}")
        severity_assessed = c3.selectbox("Officer-assessed severity", SEVERITIES, index=1, key=f"severity_assessed_{case_id}")
        observed_conditions = st.text_area("Observed conditions / measurements *", max_chars=5000, placeholder="Describe visible site conditions, dimensions, water depth, blockage, road condition, smell, nearby infrastructure, etc.", key=f"observed_{case_id}")
        investigation_findings = st.text_area("Investigation findings / likely root cause *", max_chars=4000, placeholder="Record evidence and reasoning; distinguish confirmed findings from assumptions.", key=f"findings_{case_id}")
        c4, c5 = st.columns(2)
        people_affected = c4.number_input("Estimated people potentially affected (estimate)", min_value=0, max_value=1000000, value=0, step=1, key=f"people_{case_id}")
        environment_conditions = c5.text_input("Weather / environmental conditions", max_chars=500, key=f"environment_{case_id}")
        immediate_safety_actions = st.text_area("Immediate safety / containment actions", max_chars=2000, placeholder="Barriers, warning sign, cordon, referral to emergency service, or 'none' with reason.", key=f"safety_{case_id}")
        action_taken = st.text_area("Action taken during the visit *", max_chars=4000, placeholder="Who did what, when, and what changed at the site?", key=f"field_action_{case_id}")
        materials_used = st.text_area("Materials / equipment used", max_chars=1500, key=f"materials_{case_id}")
        department_referral = st.text_input("Department / external agency referral", max_chars=500, key=f"referral_{case_id}")
        pending_work = st.text_area("Pending work, blockers, or dependencies", max_chars=2500, key=f"pending_{case_id}")
        recommendations = st.text_area("Recommendations / next accountable action *", max_chars=3000, placeholder="State the recommended owner, task, and expected timeframe.", key=f"recommendations_{case_id}")
        c6, c7 = st.columns(2)
        citizen_contacted = c6.selectbox("Citizen / site contact", ["Contacted", "Attempted, no response", "Not contacted", "Not applicable"], key=f"citizen_contacted_{case_id}")
        follow_up_required = c7.checkbox("Follow-up inspection required", value=False, key=f"followup_required_{case_id}")
        c8, c9 = st.columns(2)
        follow_up_date = c8.date_input("Follow-up due date", value=date.today() + timedelta(days=3), key=f"followup_date_{case_id}")
        citizen_feedback = c9.text_input("Citizen / contact feedback (if provided)", max_chars=1000, key=f"citizen_feedback_{case_id}")
        conclusion = st.text_area("Officer conclusion", max_chars=2000, key=f"conclusion_{case_id}")
        additional_notes = st.text_area("Additional notes", max_chars=2000, key=f"additional_notes_{case_id}")
        report_files = st.file_uploader("Attach investigation photos / documents", type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "mp4", "mov", "pdf"], accept_multiple_files=True, key=f"investigation_upload_{case_id}")
        save_report = st.form_submit_button("💾 Save investigation report", type="primary", use_container_width=True)
    if save_report:
        fields = {
            "visit_datetime": f"{visit_date.isoformat()} {visit_time.strftime('%H:%M')}",
            "inspection_result": inspection_result, "location_confirmed": location_confirmed,
            "observed_conditions": observed_conditions.strip(), "investigation_findings": investigation_findings.strip(),
            "severity_assessed": severity_assessed, "people_affected": int(people_affected),
            "environment_conditions": environment_conditions.strip(), "immediate_safety_actions": immediate_safety_actions.strip(),
            "action_taken": action_taken.strip(), "materials_used": materials_used.strip(),
            "department_referral": department_referral.strip(), "pending_work": pending_work.strip(),
            "recommendations": recommendations.strip(), "citizen_contacted": citizen_contacted,
            "citizen_feedback": citizen_feedback.strip(), "follow_up_required": bool(follow_up_required),
            "follow_up_date": follow_up_date.isoformat() if follow_up_required else "Not required",
            "conclusion": conclusion.strip(), "additional_notes": additional_notes.strip(),
        }
        ok, msg, report_id = save_investigation_report(user, case_id, fields)
        if ok:
            for file_item in uploaded_files(report_files):
                add_evidence(user["username"], case_id, file_item["filename"], file_item["mime_type"], file_item["data"], f"Investigation evidence · {report_id}")
        notice(msg, "success" if ok else "error")
        st.rerun()

    st.subheader("🧾 Case status update")
    with st.form(f"officer_update_form_{case_id}"):
        status = st.selectbox("Update status", STATUSES, index=STATUSES.index(case["status"]) if case["status"] in STATUSES else 0, key=f"officer_status_{case_id}")
        action_taken_update = st.text_area("Operational action taken (required to resolve)", value=case.get("action_taken", ""), max_chars=2000, key=f"officer_action_update_{case_id}")
        remarks = st.text_area("Officer remarks / next steps", value=case.get("remarks", ""), max_chars=2000, key=f"officer_remarks_{case_id}")
        attachments = st.file_uploader("Attach general case update evidence", type=["png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "mp4", "mov", "pdf"], accept_multiple_files=True, key=f"officer_evidence_{case_id}")
        save = st.form_submit_button("Save status update", type="primary")
    if save:
        ok, msg = update_complaint(user, case_id, status, action_taken_update, remarks, uploaded_files(attachments))
        notice(msg, "success" if ok else "error")
        st.rerun()
    if st.button("Forward to Representative / escalate", key=f"escalate_{case_id}"):
        ok, msg = update_complaint(user, case_id, "Escalated", case.get("action_taken", ""), (case.get("remarks", "") + "\nOfficer requested representative guidance.").strip())
        notice(msg, "success" if ok else "error")
        st.rerun()

    saved_reports = list_investigation_reports(user, case_id)
    if saved_reports:
        st.subheader("📥 Download saved investigation reports")
        for report in saved_reports:
            with st.container(border=True):
                st.markdown(f"**{report['id']}** · {report.get('created_at')} · {report.get('fields', {}).get('inspection_result', 'Inspection report')}")
                st.write(report.get("fields", {}).get("recommendations", ""))
                st.download_button("Download investigation report (PDF)", data=investigation_report_pdf(report), file_name=f"{report['id']}.pdf", mime="application/pdf", key=f"officer_report_pdf_{report['id']}")

def render_admin(user: dict[str, Any]) -> None:
    st.title("🛡️ Admin Control Centre")
    st.write("Manage accounts, publish official area advisories, coordinate field action, and audit service delivery.")
    render_metrics(user)
    all_cases = list_complaints(user)
    tab_overview, tab_assign, tab_hotspots, tab_reports, tab_users, tab_audit = st.tabs([
        "Overview & reports", "Assignment & case control", "Hotspot & citizen alerts",
        "Investigation reports", "User management", "Audit trail"
    ])
    with tab_overview:
        render_incident_map(user, all_cases)
        st.subheader("All complaints")
        st.dataframe(table_for_cases(all_cases), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download privacy-conscious CSV", data=export_csv(all_cases), file_name=f"swasthyagrid_reports_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
        if all_cases:
            counts = pd.DataFrame([{"Status": status, "Reports": sum(c["status"] == status for c in all_cases)} for status in STATUSES])
            st.subheader("Workflow status distribution")
            st.bar_chart(counts.set_index("Status"))
        active_alerts = list_hotspot_alerts(user)
        st.metric("Active official hotspot advisories", len(active_alerts))
        st.caption("Admin-published advisories create in-app notifications for active Citizen accounts whose jurisdiction matches the alert (or all citizens for an All Areas notice).")

    with tab_assign:
        if not all_cases:
            st.info("No complaints yet. A citizen report can be created to test assignment.")
        else:
            cid = st.selectbox("Complaint", [c["id"] for c in all_cases], key="admin_assign_case")
            case = get_complaint(cid)
            officers = list_users("Field Officer")
            reps = list_users("Representative")
            officer_names = [""] + [u["username"] for u in officers]
            rep_names = [""] + [u["username"] for u in reps]
            with st.form("assignment_form"):
                officer = st.selectbox("Assign Field Officer", officer_names, index=officer_names.index(case["assigned_officer"]) if case and case["assigned_officer"] in officer_names else 0)
                representative = st.selectbox("Assign Representative", rep_names, index=rep_names.index(case["representative"]) if case and case["representative"] in rep_names else 0)
                assign = st.form_submit_button("Save assignment", type="primary")
            if assign:
                ok, msg = assign_complaint(user["username"], cid, officer, representative)
                notice(msg, "success" if ok else "error")
                st.rerun()
            if case:
                st.markdown(f"**{cid} · {case['title']}** — {case['status']}")
                st.write(case["description"])
                with st.form("admin_status_form"):
                    status = st.selectbox("Admin status override", STATUSES, index=STATUSES.index(case["status"]) if case["status"] in STATUSES else 0)
                    action = st.text_area("Action taken", value=case.get("action_taken", ""))
                    remarks = st.text_area("Admin remarks", value=case.get("remarks", ""))
                    update = st.form_submit_button("Update case status")
                if update:
                    ok, msg = update_complaint(user, cid, status, action, remarks)
                    notice(msg, "success" if ok else "error")
                    st.rerun()

    with tab_hotspots:
        st.subheader("📣 Publish an official hotspot / public advisory")
        st.info("Publishing sends a persistent in-app notification to Citizen accounts in the selected jurisdiction. It does not send SMS, WhatsApp, or push messages unless separately integrated.")
        user_rows = list_users()
        cases = list_complaints(user)
        area_values = {u.get("jurisdiction", "") for u in user_rows if u.get("jurisdiction")}
        area_values.update(c.get("area", "") for c in cases if c.get("area"))
        area_options = ["All Areas"] + sorted(a for a in area_values if a and a.lower() not in {"all areas", "all wards", "public"})
        with st.form("admin_publish_hotspot_form", clear_on_submit=True):
            alert_title = st.text_input("Alert title *", placeholder="e.g. Stagnant water inspection advisory", max_chars=150)
            c1, c2 = st.columns(2)
            alert_category = c1.selectbox("Issue category", CATEGORY_OPTIONS, key="admin_alert_category")
            alert_severity = c2.selectbox("Alert severity", SEVERITIES, index=2, key="admin_alert_severity")
            alert_area = st.selectbox("Affected ward / scope *", area_options)
            alert_description = st.text_area("Public-facing alert details *", max_chars=3000, placeholder="What area is affected, what has been observed, when it was last checked, and what residents should know.")
            alert_precautions = st.text_area("Precautions / recommended actions", max_chars=2500, placeholder="For example: avoid the cordoned road segment; report overflowing water to the listed service channel.")
            alert_source = st.text_input("Source / verification note", value="Admin reviewed", max_chars=300)
            with st.expander("📍 Add hotspot map coordinates (optional)"):
                st.caption("Coordinates are displayed on the map. Use an approximate public point or area centroid; do not publish a citizen's exact home location.")
                lat_col, lon_col = st.columns(2)
                alert_lat_input = lat_col.number_input("Latitude (0 = not set)", min_value=-90.0, max_value=90.0, value=0.0, format="%.6f", key="alert_latitude")
                alert_lon_input = lon_col.number_input("Longitude (0 = not set)", min_value=-180.0, max_value=180.0, value=0.0, format="%.6f", key="alert_longitude")
            ex1, ex2 = st.columns(2)
            alert_expiry_date = ex1.date_input("Advisory expiry date", value=date.today() + timedelta(days=7))
            alert_expiry_time = ex2.time_input("Expiry time (UTC)", value=time(23, 59))
            st.caption("Publishing creates a public advisory and queues in-app notifications for Citizen accounts in the affected area. Choose 'All Areas' to notify all active Citizen accounts.")
            publish = st.form_submit_button("🚨 Publish hotspot & notify citizens", type="primary", use_container_width=True)
        if publish:
            latitude = float(alert_lat_input) if alert_lat_input != 0.0 or alert_lon_input != 0.0 else None
            longitude = float(alert_lon_input) if latitude is not None else None
            expires_at = datetime.combine(alert_expiry_date, alert_expiry_time).replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
            ok, msg, alert_id = create_hotspot_alert(user, alert_title, alert_category, alert_severity, alert_area,
                                                      alert_description, alert_precautions, latitude, longitude,
                                                      alert_source, expires_at, True)
            notice(msg, "success" if ok else "error")
            st.rerun()

        st.divider()
        st.subheader("Manage published hotspot advisories")
        all_alerts = list_hotspot_alerts(user, include_closed=True)
        if all_alerts:
            view_df = pd.DataFrame([{k: a.get(k) for k in ["id", "title", "category", "severity", "area", "status", "source", "created_by", "created_at", "expires_at", "closure_reason"]} for a in all_alerts])
            st.dataframe(view_df, use_container_width=True, hide_index=True)
            active_alerts = [a for a in all_alerts if a.get("status") == "Active"]
            if active_alerts:
                active_by_id = {a["id"]: a for a in active_alerts}
                selected_alert_id = st.selectbox("Select active advisory to close", list(active_by_id), format_func=lambda x: f"{x} · {active_by_id[x]['title']} · {active_by_id[x]['area']}")
                closure_reason = st.text_input("Closure reason / review outcome", placeholder="e.g. Field team verified the hazard was removed")
                if st.button("Close selected hotspot and notify citizens", type="secondary"):
                    ok, msg = close_hotspot_alert(user, selected_alert_id, closure_reason)
                    notice(msg, "success" if ok else "error")
                    st.rerun()
        else:
            st.caption("No Admin-published hotspot alerts yet.")

    with tab_reports:
        st.subheader("📋 Field investigation report review")
        investigation_reports = list_investigation_reports(user, limit=500)
        if not investigation_reports:
            st.info("Investigation reports submitted by Field Officers will appear here with PDF downloads.")
        else:
            report_rows = [{"Report ID": r["id"], "Case ID": r["complaint_id"], "Title": r.get("complaint_title"), "Area": r.get("complaint_area"), "Officer": r.get("officer_username"), "Inspection outcome": r.get("fields", {}).get("inspection_result"), "Created": r.get("created_at")} for r in investigation_reports]
            st.dataframe(pd.DataFrame(report_rows), use_container_width=True, hide_index=True)
            st.download_button("Download investigation report index (CSV)", data=pd.DataFrame(report_rows).to_csv(index=False).encode("utf-8-sig"), file_name="swasthyagrid_investigation_index.csv", mime="text/csv")
            report_ids = [r["id"] for r in investigation_reports]
            chosen_report_id = st.selectbox("Choose investigation report", report_ids, format_func=lambda x: next((f"{x} · {r.get('complaint_title','')}" for r in investigation_reports if r["id"] == x), x))
            chosen_report = next((r for r in investigation_reports if r["id"] == chosen_report_id), None)
            if chosen_report:
                st.json(chosen_report.get("fields", {}))
                st.download_button("⬇️ Download full field investigation PDF", data=investigation_report_pdf(chosen_report), file_name=f"{chosen_report_id}.pdf", mime="application/pdf", key=f"admin_inv_pdf_{chosen_report_id}")

    with tab_users:
        st.subheader("Create account")
        with st.form("create_user_form"):
            c1, c2 = st.columns(2)
            username = c1.text_input("User ID", max_chars=60)
            full_name = c2.text_input("Full name", max_chars=100)
            c3, c4 = st.columns(2)
            role = c3.selectbox("Role", list(ROLES))
            jurisdiction = c4.text_input("Ward / jurisdiction", value="Central Ward", max_chars=100)
            password = st.text_input("Temporary password (minimum 10 characters)", type="password", max_chars=200)
            create = st.form_submit_button("Create account", type="primary")
        if create:
            ok, msg = create_user(user["username"], username, password, role, full_name, jurisdiction)
            notice(msg, "success" if ok else "error")
            st.rerun()
        st.subheader("Current users")
        st.dataframe(pd.DataFrame(list_users()).drop(columns=["id", "active"], errors="ignore"), use_container_width=True, hide_index=True)
    with tab_audit:
        st.subheader("Recent system audit events")
        st.dataframe(pd.DataFrame(audit_events()), use_container_width=True, hide_index=True)

def render_representative(user: dict[str, Any]) -> None:
    title = "MLA" if "mla" in user.get("full_name", "").lower() else "Representative"
    st.title(f"🏛️ Welcome, {title}")
    st.write(f"Oversight area: **{user.get('jurisdiction', 'General')}**. Review escalations and service outcomes without exposing unnecessary citizen details.")
    render_metrics(user)
    cases = list_complaints(user)
    with st.expander("🗺️ Constituency map & hotspot signals", expanded=True):
        render_incident_map(user, cases)
    st.subheader("Oversight and escalated reports")
    st.dataframe(table_for_cases(cases), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download oversight report", data=export_csv(cases), file_name=f"oversight_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
    oversight_investigations = list_investigation_reports(user, limit=300)
    if oversight_investigations:
        st.subheader("Field investigation reports for your oversight area")
        st.dataframe(pd.DataFrame([{"Report ID": r["id"], "Case ID": r["complaint_id"], "Title": r.get("complaint_title"), "Area": r.get("complaint_area"), "Inspection outcome": r.get("fields", {}).get("inspection_result"), "Saved at": r.get("created_at")} for r in oversight_investigations]), use_container_width=True, hide_index=True)
        chosen_id = st.selectbox("Download an investigation report", [r["id"] for r in oversight_investigations], key="rep_inv_select")
        chosen = next((r for r in oversight_investigations if r["id"] == chosen_id), None)
        if chosen:
            st.download_button("Download investigation PDF", data=investigation_report_pdf(chosen), file_name=f"{chosen_id}.pdf", mime="application/pdf", key=f"rep_inv_pdf_{chosen_id}")
    if cases:
        cid = st.selectbox("Open a case for oversight", [c["id"] for c in cases], key="rep_case_select")
        case = get_complaint(cid)
        if case:
            st.markdown(f"### {case['id']} · {case['title']}")
            st.write(f"**Status:** {case['status']} · **Risk:** {case['risk_level']} · **Area:** {case['area']}")
            st.write(case["description"])
            if case.get("action_taken"):
                st.write(f"**Action taken:** {case['action_taken']}")
            render_evidence(user, cid)
            with st.form("rep_guidance_form"):
                guidance = st.text_area("Representative guidance / oversight note", value=case.get("remarks", ""), max_chars=2000)
                send = st.form_submit_button("Save oversight note")
            if send:
                ok, msg = update_complaint(user, cid, case["status"], case.get("action_taken", ""), guidance)
                notice(msg, "success" if ok else "error")
                st.rerun()


def main() -> None:
    init_db()
    show_notice()
    if "sg_user" not in st.session_state:
        render_login()
        return
    user = st.session_state["sg_user"]
    fresh = get_user(user["username"])
    if not fresh or not fresh.get("active"):
        st.session_state.pop("sg_user", None)
        st.error("This account is inactive. Please contact the Admin.")
        st.rerun()
    user.update({k: fresh[k] for k in ("role", "full_name", "jurisdiction", "active")})
    with st.sidebar:
        st.markdown("# 🌐 SwasthyaGrid")
        st.caption("Civic Intelligence Platform")
        st.divider()
        st.write(f"**{user['full_name']}**")
        st.caption(f"{user['role']} · {user['jurisdiction']}")
        if st.button("Sign out", use_container_width=True):
            st.session_state.pop("sg_user", None)
            st.rerun()
        st.divider()
        st.caption("Civic Intelligence Platform")
        if user["role"] != "Citizen":
            render_staff_inbox(user)
        st.caption("AI is advisory. Hotspots are signals, not confirmed outbreaks. For immediate danger, contact local emergency services.")
    if user["role"] == "Citizen":
        render_citizen(user)
    elif user["role"] == "Field Officer":
        render_officer(user)
    elif user["role"] == "Admin":
        render_admin(user)
    elif user["role"] == "Representative":
        render_representative(user)
    else:
        st.error("Unknown role. Contact your administrator.")


if __name__ == "__main__":
    main()

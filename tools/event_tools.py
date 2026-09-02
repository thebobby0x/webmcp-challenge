"""
Event data tools for the eventOS agent fleet.
Mock data based on IMEX America — 10,000 attendees, 3,500 exhibitors, 15,000 meetings.
"""

import random
from datetime import datetime, timedelta
from typing import Any

# ─── Mock Data ────────────────────────────────────────────────────────────────

MOCK_MEETINGS = [
    {"id": f"MTG-{i:04d}", "attendee": f"attendee_{i}@corp.com",
     "exhibitor": f"exhibitor_{i % 350}@brand.com",
     "start": (datetime(2026, 10, 13, 9, 0) + timedelta(minutes=30 * (i % 20))).isoformat(),
     "duration_min": 30, "booth": f"B-{1000 + i % 500}", "status": "confirmed"}
    for i in range(1, 501)  # 500 sample meetings
]

MOCK_EXHIBITORS = [
    {"id": f"EXH-{i:04d}", "company": f"TechCorp {i}", "booth": f"B-{1000 + i}",
     "category": random.choice(["Tech", "F&B", "AV", "Logistics", "Hospitality"]),
     "setup_confirmed": i % 5 != 0,  # 20% haven't confirmed
     "region": random.choice(["NA", "EMEA", "APAC", "LATAM"])}
    for i in range(1, 201)
]

MOCK_ATTENDEES = [
    {"id": f"ATT-{i:04d}", "email": f"attendee_{i}@corp.com",
     "name": f"Attendee {i}", "vip": i % 50 == 0,
     "sessions_registered": random.randint(1, 8),
     "notification_pref": random.choice(["email", "sms", "push"])}
    for i in range(1, 301)
]

MOCK_VENDORS = [
    {"id": f"VND-{i:04d}", "name": f"Vendor {i}",
     "type": random.choice(["F&B", "AV", "Security", "Logistics", "Cleaning"]),
     "deliverable": f"Deliverable {i}", "due": "2026-10-12T08:00:00",
     "status": random.choice(["on-track", "at-risk", "delayed"])}
    for i in range(1, 51)
]

# ─── Tool Functions ───────────────────────────────────────────────────────────

def get_meetings_by_exhibitor(exhibitor_id: str) -> list[dict]:
    """Get all scheduled meetings for a specific exhibitor."""
    return [m for m in MOCK_MEETINGS if exhibitor_id in m["exhibitor"]]


def get_conflicting_meetings(attendee_id: str) -> list[dict]:
    """Detect scheduling conflicts for a given attendee across all their meetings."""
    attendee_meetings = [m for m in MOCK_MEETINGS if attendee_id in m["attendee"]]
    conflicts = []
    for i, m1 in enumerate(attendee_meetings):
        for m2 in attendee_meetings[i + 1:]:
            t1 = datetime.fromisoformat(m1["start"])
            t2 = datetime.fromisoformat(m2["start"])
            if abs((t1 - t2).total_seconds()) < m1["duration_min"] * 60:
                conflicts.append({"meeting_1": m1["id"], "meeting_2": m2["id"],
                                   "overlap_minutes": m1["duration_min"] - abs((t1 - t2).total_seconds()) / 60})
    return conflicts


def reschedule_meeting(meeting_id: str, new_start: str) -> dict:
    """Reschedule a meeting to a new time slot."""
    for m in MOCK_MEETINGS:
        if m["id"] == meeting_id:
            old_start = m["start"]
            m["start"] = new_start
            return {"success": True, "meeting_id": meeting_id,
                    "old_start": old_start, "new_start": new_start}
    return {"success": False, "error": f"Meeting {meeting_id} not found"}


def get_unconfirmed_exhibitors(region: str | None = None) -> list[dict]:
    """Get exhibitors who haven't confirmed their booth setup."""
    unconfirmed = [e for e in MOCK_EXHIBITORS if not e["setup_confirmed"]]
    if region:
        unconfirmed = [e for e in unconfirmed if e["region"] == region]
    return unconfirmed


def get_event_snapshot() -> dict:
    """Get a real-time snapshot of event KPIs for executive briefing."""
    confirmed = sum(1 for m in MOCK_MEETINGS if m["status"] == "confirmed")
    vip_count = sum(1 for a in MOCK_ATTENDEES if a["vip"])
    at_risk_vendors = [v for v in MOCK_VENDORS if v["status"] in ("at-risk", "delayed")]
    return {
        "total_meetings": len(MOCK_MEETINGS),
        "confirmed_meetings": confirmed,
        "confirmation_rate_pct": round(confirmed / len(MOCK_MEETINGS) * 100, 1),
        "total_exhibitors": len(MOCK_EXHIBITORS),
        "unconfirmed_exhibitors": sum(1 for e in MOCK_EXHIBITORS if not e["setup_confirmed"]),
        "total_attendees": len(MOCK_ATTENDEES),
        "vip_attendees": vip_count,
        "vendor_at_risk": len(at_risk_vendors),
        "at_risk_vendors": [v["name"] for v in at_risk_vendors],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def get_vendor_sla_breaches() -> list[dict]:
    """Get vendors who have missed or are at risk of missing SLA deadlines."""
    return [v for v in MOCK_VENDORS if v["status"] in ("at-risk", "delayed")]


def check_gdpr_compliance(data: dict) -> dict:
    """
    Inline GDPR/CCPA compliance check. Redacts PII fields before agent output.
    Returns sanitized data + compliance report.
    """
    pii_fields = {"email", "phone", "address", "name", "ssn"}
    violations = []
    sanitized = {}
    for key, value in data.items():
        if key.lower() in pii_fields:
            sanitized[key] = "[REDACTED]"
            violations.append(f"PII field '{key}' redacted per GDPR Article 5(1)(f)")
        else:
            sanitized[key] = value
    return {
        "compliant": len(violations) == 0,
        "violations": violations,
        "sanitized_data": sanitized,
        "processed_at": datetime.utcnow().isoformat() + "Z",
    }

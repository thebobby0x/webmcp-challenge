"""
Agent Registry — eventOS Enterprise Fleet
Central catalog of all agents: versioning, discovery, status, and health.
Required by the Fortified Enterprise Fleet track.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal


AgentStatus = Literal["active", "idle", "error", "disabled"]


@dataclass
class AgentRecord:
    name: str
    role: str
    description: str
    version: str
    status: AgentStatus
    model: str
    last_run: str | None = None
    task_count: int = 0
    error_count: int = 0
    tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def mark_run(self, success: bool = True) -> None:
        self.last_run = datetime.utcnow().isoformat() + "Z"
        self.task_count += 1
        if not success:
            self.error_count += 1
        self.status = "active" if success else "error"

    @property
    def health_score(self) -> float:
        if self.task_count == 0:
            return 100.0
        return round((1 - self.error_count / self.task_count) * 100, 1)


# ─── Registry Definition ──────────────────────────────────────────────────────

AGENT_REGISTRY: dict[str, AgentRecord] = {
    "BookingAgent": AgentRecord(
        name="BookingAgent",
        role="Meeting Orchestration",
        description="Detects scheduling conflicts, reroutes meetings asynchronously, sends confirmations.",
        version="1.0.0",
        status="active",
        model="gemini-2.0-flash",
        tools=["get_conflicting_meetings", "reschedule_meeting", "get_meetings_by_exhibitor", "send_notification"],
        tags=["scheduling", "async", "enterprise"],
    ),
    "CommsAgent": AgentRecord(
        name="CommsAgent",
        role="Attendee Communications",
        description="Routes notifications through email/SMS/push. Escalates when human authority required.",
        version="1.0.0",
        status="active",
        model="gemini-2.0-flash",
        tools=["send_notification", "escalate_to_human", "get_notification_history", "check_gdpr_compliance"],
        tags=["communications", "routing", "gdpr"],
    ),
    "InsightAgent": AgentRecord(
        name="InsightAgent",
        role="Real-Time Intelligence",
        description="Processes event KPIs, generates executive briefings, flags anomalies proactively.",
        version="1.0.0",
        status="active",
        model="gemini-2.0-flash",
        tools=["get_event_snapshot", "get_unconfirmed_exhibitors", "get_vendor_sla_breaches"],
        tags=["analytics", "monitoring", "executive"],
    ),
    "ComplianceAgent": AgentRecord(
        name="ComplianceAgent",
        role="GDPR/CCPA Enforcement",
        description="Inline compliance guardrail on all agent data interactions. Zero PII leaks by design.",
        version="1.0.0",
        status="active",
        model="gemini-2.0-flash",
        tools=["check_gdpr_compliance"],
        tags=["compliance", "gdpr", "ccpa", "security"],
    ),
    "VendorAgent": AgentRecord(
        name="VendorAgent",
        role="Vendor SLA Management",
        description="Tracks F&B/AV/logistics vendors. Sends reminders. Flags SLA breaches before they escalate.",
        version="1.0.0",
        status="active",
        model="gemini-2.0-flash",
        tools=["get_vendor_sla_breaches", "send_notification", "escalate_to_human"],
        tags=["vendors", "sla", "operations"],
    ),
}


def get_registry() -> list[dict]:
    """Return all agents as a list of dicts for API serialization."""
    return [
        {**record.to_dict(), "health_score": record.health_score}
        for record in AGENT_REGISTRY.values()
    ]


def get_agent(name: str) -> AgentRecord | None:
    """Get a specific agent record by name."""
    return AGENT_REGISTRY.get(name)


def update_agent_status(name: str, status: AgentStatus) -> bool:
    """Update an agent's status in the registry."""
    if name in AGENT_REGISTRY:
        AGENT_REGISTRY[name].status = status
        return True
    return False

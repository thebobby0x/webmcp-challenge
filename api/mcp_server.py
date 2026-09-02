"""
MCP server for the eventOS Agent Fleet.

Speaks Model Context Protocol over Streamable HTTP at /mcp:
JSON-RPC 2.0 request/response, protocol-version negotiation, tool discovery
(tools/list) and tool invocation (tools/call).

The 5-agent fleet already exposes its capabilities as plain Python functions
(tools/event_tools.py, tools/notification_tools.py). This module is the
protocol skin over them — it does not reimplement any agent logic.

Transport notes:
  POST /mcp    JSON-RPC request -> JSON response (or SSE if the client only
               accepts text/event-stream). Notifications get 202 + empty body.
  GET  /mcp    Server-initiated SSE stream (bounded keepalive).
  DELETE /mcp  Session termination.

Sessions are issued on initialize but not enforced, so the endpoint works for
stateless clients (curl, fetch from a browser) as well as session-aware ones.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from registry.agent_registry import AGENT_REGISTRY, get_registry
from tools.event_tools import (
    MOCK_ATTENDEES,
    MOCK_MEETINGS,
    MOCK_VENDORS,
    check_gdpr_compliance,
    get_conflicting_meetings,
    get_event_snapshot,
    get_meetings_by_exhibitor,
    get_unconfirmed_exhibitors,
    get_vendor_sla_breaches,
    reschedule_meeting,
)
from tools.notification_tools import (
    escalate_to_human,
    get_notification_history,
    send_notification,
)

router = APIRouter()


# ─── Protocol constants ───────────────────────────────────────────────────────

SERVER_NAME = "eventos-agent-fleet"
SERVER_VERSION = "1.1.0"

# Newest first. On initialize we echo the client's version when we speak it,
# otherwise we answer with LATEST_PROTOCOL_VERSION and let the client decide.
SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26"]
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

# JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Live sessions: session_id -> metadata. Advisory only (see module docstring).
SESSIONS: dict[str, dict] = {}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ─── Tool implementations ─────────────────────────────────────────────────────
#
# Each returns (summary_text, structured_payload). The summary is what an LLM
# reads in content[]; the payload is returned as structuredContent for UIs.


def _t_detect_conflicts(args: dict) -> tuple[str, dict]:
    attendee_id = args["attendee_id"]
    conflicts = get_conflicting_meetings(attendee_id)
    summary = (
        f"BookingAgent found {len(conflicts)} scheduling conflict(s) for {attendee_id}."
        if conflicts
        else f"BookingAgent found no scheduling conflicts for {attendee_id}."
    )
    return summary, {
        "attendee_id": attendee_id,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "agent": "BookingAgent",
    }


def _next_free_slot(attendee_id: str) -> str:
    """Pick the first 30-minute slot on Day 1 that the attendee has free."""
    booked = {
        datetime.fromisoformat(m["start"])
        for m in MOCK_MEETINGS
        if attendee_id in m["attendee"]
    }
    slot = datetime(2026, 10, 13, 9, 0)
    while slot in booked:
        slot += timedelta(minutes=30)
    return slot.isoformat()


def _t_schedule_meeting(args: dict) -> tuple[str, dict]:
    """Reschedule an existing meeting, or book a new one into the next free slot."""
    meeting_id = args.get("meeting_id")
    new_start = args.get("new_start")

    if meeting_id and new_start:
        result = reschedule_meeting(meeting_id, new_start)
        if not result.get("success"):
            raise ToolError(result.get("error", f"Meeting {meeting_id} not found"))
        AGENT_REGISTRY["BookingAgent"].mark_run(success=True)
        return (
            f"BookingAgent rescheduled {meeting_id} from {result['old_start']} "
            f"to {result['new_start']}.",
            {"action": "rescheduled", **result, "agent": "BookingAgent"},
        )

    attendee_id = args.get("attendee_id") or "ATT-0001"
    exhibitor_id = args.get("exhibitor_id") or "exhibitor_1@brand.com"
    duration = int(args.get("duration_min") or 30)
    start = new_start or _next_free_slot(attendee_id)

    meeting = {
        "id": f"MTG-{len(MOCK_MEETINGS) + 1:04d}",
        "attendee": attendee_id,
        "exhibitor": exhibitor_id,
        "start": start,
        "duration_min": duration,
        "booth": args.get("booth") or "B-1000",
        "status": "confirmed",
    }
    MOCK_MEETINGS.append(meeting)
    AGENT_REGISTRY["BookingAgent"].mark_run(success=True)

    meeting_type = args.get("meeting_type") or "standard"
    return (
        f"BookingAgent booked {meeting['id']} ({meeting_type}) for {attendee_id} "
        f"with {exhibitor_id} at {start} for {duration} minutes.",
        {
            "action": "booked",
            "meeting": meeting,
            "meeting_type": meeting_type,
            "event_id": args.get("event_id"),
            "agent": "BookingAgent",
        },
    )


def _t_exhibitor_meetings(args: dict) -> tuple[str, dict]:
    exhibitor_id = args["exhibitor_id"]
    limit = int(args.get("limit") or 25)
    meetings = get_meetings_by_exhibitor(exhibitor_id)
    shown = meetings[:limit]
    return (
        f"BookingAgent found {len(meetings)} meeting(s) for exhibitor "
        f"{exhibitor_id} (showing {len(shown)}).",
        {
            "exhibitor_id": exhibitor_id,
            "total": len(meetings),
            "meetings": shown,
            "agent": "BookingAgent",
        },
    )


def _t_analyze_event(args: dict) -> tuple[str, dict]:
    """InsightAgent executive briefing — same analysis the /demo/insight route runs."""
    snapshot = get_event_snapshot()
    focus = args.get("focus") or "overall"
    query = args.get("query") or "Give me an executive briefing on current event health."
    at_risk = snapshot["vendor_at_risk"]

    headline = (
        f"Event health: {snapshot['confirmation_rate_pct']}% meeting confirmation rate. "
        f"{snapshot['unconfirmed_exhibitors']} exhibitors unconfirmed. "
        f"{at_risk} vendor(s) at risk."
    )
    recommendations = [
        f"Contact {snapshot['unconfirmed_exhibitors']} unconfirmed exhibitors "
        "immediately — 24hr to show opening.",
        f"Activate backup protocols for {at_risk} at-risk vendor(s) — "
        "do not wait for SLA breach.",
        "VIP pre-event briefing at 08:00 Day 1 — confirm schedule with event director.",
    ]
    if focus == "vendors":
        recommendations = [recommendations[1]]
    elif focus == "exhibitors":
        recommendations = [recommendations[0]]
    elif focus == "meetings":
        recommendations = [
            f"{snapshot['confirmed_meetings']} of {snapshot['total_meetings']} meetings "
            "confirmed — chase the remainder through CommsAgent."
        ]

    AGENT_REGISTRY["InsightAgent"].mark_run(success=True)
    return (
        f"{headline}\n\nRecommendations:\n"
        + "\n".join(f"- {r}" for r in recommendations),
        {
            "query": query,
            "focus": focus,
            "headline": headline,
            "kpis": snapshot,
            "recommendations": recommendations,
            "agent": "InsightAgent",
        },
    )


def _t_unconfirmed_exhibitors(args: dict) -> tuple[str, dict]:
    region = args.get("region")
    limit = int(args.get("limit") or 25)
    exhibitors = get_unconfirmed_exhibitors(region)
    shown = exhibitors[:limit]
    scope = f" in {region}" if region else ""
    AGENT_REGISTRY["InsightAgent"].mark_run(success=True)
    return (
        f"InsightAgent found {len(exhibitors)} unconfirmed exhibitor(s){scope} "
        f"(showing {len(shown)}).",
        {
            "region": region,
            "total": len(exhibitors),
            "exhibitors": shown,
            "agent": "InsightAgent",
        },
    )


def _t_send_notification(args: dict) -> tuple[str, dict]:
    attendee_id = args["attendee_id"]
    message = args["message"]
    channel = args.get("channel")
    if not channel:
        match = next((a for a in MOCK_ATTENDEES if a["id"] == attendee_id), None)
        channel = match["notification_pref"] if match else "email"
    result = send_notification(
        attendee_id=attendee_id,
        channel=channel,
        message=message,
        priority=args.get("priority") or "normal",
    )
    AGENT_REGISTRY["CommsAgent"].mark_run(success=True)
    return (
        f"CommsAgent delivered {result['message_id']} to {attendee_id} via {channel} "
        f"({result['priority']} priority).",
        {**result, "agent": "CommsAgent"},
    )


def _t_escalate(args: dict) -> tuple[str, dict]:
    result = escalate_to_human(
        issue=args["issue"],
        attendee_id=args.get("attendee_id") or "unassigned",
        context=args.get("context") or {},
    )
    AGENT_REGISTRY["CommsAgent"].mark_run(success=True)
    return (
        f"CommsAgent escalated to a human coordinator. Ticket {result['ticket_id']} "
        f"assigned to {result['assigned_to']}, SLA {result['sla_response_minutes']} min.",
        {**result, "agent": "CommsAgent"},
    )


def _t_notification_history(args: dict) -> tuple[str, dict]:
    attendee_id = args["attendee_id"]
    history = get_notification_history(attendee_id, int(args.get("limit") or 10))
    return (
        f"CommsAgent returned {len(history)} notification record(s) for {attendee_id}.",
        {"attendee_id": attendee_id, "count": len(history), "history": history,
         "agent": "CommsAgent"},
    )


def _t_sla_breaches(args: dict) -> tuple[str, dict]:
    breaches = get_vendor_sla_breaches()
    vendor_type = args.get("vendor_type")
    if vendor_type:
        breaches = [v for v in breaches if v["type"].lower() == vendor_type.lower()]
    scope = f" of type {vendor_type}" if vendor_type else ""
    AGENT_REGISTRY["VendorAgent"].mark_run(success=True)
    return (
        f"VendorAgent flagged {len(breaches)} vendor(s){scope} at risk of or in SLA breach, "
        f"out of {len(MOCK_VENDORS)} tracked vendors.",
        {
            "vendor_type": vendor_type,
            "breach_count": len(breaches),
            "tracked_vendors": len(MOCK_VENDORS),
            "vendors": breaches,
            "agent": "VendorAgent",
        },
    )


def _t_check_gdpr(args: dict) -> tuple[str, dict]:
    data = args["data"]
    if not isinstance(data, dict):
        raise ToolError("'data' must be a JSON object of field name -> value")
    result = check_gdpr_compliance(data)
    AGENT_REGISTRY["ComplianceAgent"].mark_run(success=True)
    verdict = "compliant" if result["compliant"] else "non-compliant"
    return (
        f"ComplianceAgent ruled the payload {verdict}. "
        f"{len(result['violations'])} PII field(s) redacted.",
        {**result, "agent": "ComplianceAgent"},
    )


def _t_list_agents(args: dict) -> tuple[str, dict]:
    agents = get_registry()
    status = args.get("status")
    if status:
        agents = [a for a in agents if a["status"] == status]
    names = ", ".join(a["name"] for a in agents) or "none"
    return (
        f"{len(agents)} agent(s) in the eventOS fleet registry: {names}.",
        {"total": len(agents), "agents": agents, "filter_status": status},
    )


async def _t_architect_design(args: dict) -> tuple[str, dict]:
    """Live LLM call: designs a bespoke agent fleet for an event profile."""
    # Imported lazily — api.main imports this router, so a module-level import
    # would be circular.
    from api.main import ArchitectRequest, architect_fleet

    request = ArchitectRequest(
        event_name=args.get("event_name") or "IMEX America 2026",
        attendees=int(args.get("attendees") or 12000),
        exhibitors=int(args.get("exhibitors") or 3500),
        days=int(args.get("days") or 3),
        features=list(args.get("features") or []),
    )
    try:
        spec = await architect_fleet(request)
    except Exception as e:  # HTTPException included — surface as a tool error
        detail = getattr(e, "detail", None) or str(e)
        raise ToolError(f"Fleet Architect call failed: {detail}")

    roster = "\n".join(
        f"- {a['name']} ({a['priority']}): {a['role']}" for a in spec["agents"]
    )
    return (
        f"Fleet Architect designed \"{spec['fleet_name']}\" with {len(spec['agents'])} "
        f"agents for {request.event_name}.\n\n{roster}\n\n{spec['rationale']}",
        spec,
    )


class ToolError(Exception):
    """Raised by a tool when the call fails for a reason the model should see."""


# ─── Tool registry ────────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "bookingagent_detect_conflicts",
        "title": "Detect Scheduling Conflicts",
        "description": (
            "BookingAgent: find overlapping meetings for an attendee across the "
            "event schedule. Returns each conflicting pair with overlap minutes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "attendee_id": {
                    "type": "string",
                    "description": (
                        "Attendee identifier. Matched as a substring, so "
                        "'attendee_7@corp.com' targets one person and 'attendee_7' "
                        "sweeps the whole cohort sharing that prefix."
                    ),
                }
            },
            "required": ["attendee_id"],
        },
        "handler": _t_detect_conflicts,
        "agent": "BookingAgent",
    },
    {
        "name": "bookingagent_schedule_meeting",
        "title": "Schedule or Reschedule a Meeting",
        "description": (
            "BookingAgent: book a new exhibitor meeting into the attendee's next free "
            "slot, or move an existing meeting when meeting_id and new_start are given."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "attendee_id": {"type": "string", "description": "Attendee to book for, e.g. ATT-0001"},
                "exhibitor_id": {"type": "string", "description": "Exhibitor contact or booth owner"},
                "meeting_id": {"type": "string", "description": "Existing meeting to move, e.g. MTG-0007"},
                "new_start": {"type": "string", "description": "ISO 8601 start time for the meeting"},
                "duration_min": {"type": "integer", "description": "Meeting length in minutes (default 30)"},
                "booth": {"type": "string", "description": "Booth number, e.g. B-1042"},
                "meeting_type": {"type": "string", "description": "Free-form label, e.g. vendor, vip, press"},
                "event_id": {"type": "string", "description": "Optional external event reference"},
            },
        },
        "handler": _t_schedule_meeting,
        "agent": "BookingAgent",
    },
    {
        "name": "bookingagent_list_exhibitor_meetings",
        "title": "List Exhibitor Meetings",
        "description": "BookingAgent: list every scheduled meeting for one exhibitor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exhibitor_id": {"type": "string", "description": "Exhibitor identifier or email fragment"},
                "limit": {"type": "integer", "description": "Max meetings to return (default 25)"},
            },
            "required": ["exhibitor_id"],
        },
        "handler": _t_exhibitor_meetings,
        "agent": "BookingAgent",
    },
    {
        "name": "insightagent_analyze_event",
        "title": "Executive Event Briefing",
        "description": (
            "InsightAgent: real-time KPI snapshot plus a prioritised executive briefing "
            "on event health, with recommendations and a risk horizon."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question to brief against"},
                "focus": {
                    "type": "string",
                    "enum": ["overall", "vendors", "exhibitors", "meetings"],
                    "description": "Narrow the briefing to one dimension (default overall)",
                },
            },
        },
        "handler": _t_analyze_event,
        "agent": "InsightAgent",
    },
    {
        "name": "insightagent_unconfirmed_exhibitors",
        "title": "Unconfirmed Exhibitors",
        "description": (
            "InsightAgent: exhibitors that have not confirmed booth setup, "
            "optionally filtered by region."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": ["NA", "EMEA", "APAC", "LATAM"],
                    "description": "Restrict to one region",
                },
                "limit": {"type": "integer", "description": "Max exhibitors to return (default 25)"},
            },
        },
        "handler": _t_unconfirmed_exhibitors,
        "agent": "InsightAgent",
    },
    {
        "name": "commsagent_send_notification",
        "title": "Send Attendee Notification",
        "description": (
            "CommsAgent: deliver a message to an attendee. Channel defaults to the "
            "attendee's stored preference (email, sms or push)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "attendee_id": {"type": "string", "description": "Recipient, e.g. ATT-0001"},
                "message": {"type": "string", "description": "Notification body"},
                "channel": {
                    "type": "string",
                    "enum": ["email", "sms", "push"],
                    "description": "Override the attendee's preferred channel",
                },
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high", "urgent"],
                    "description": "Delivery priority (default normal)",
                },
            },
            "required": ["attendee_id", "message"],
        },
        "handler": _t_send_notification,
        "agent": "CommsAgent",
    },
    {
        "name": "commsagent_escalate_to_human",
        "title": "Escalate to Human Coordinator",
        "description": (
            "CommsAgent: hand an issue the fleet cannot resolve autonomously to a "
            "human event coordinator. Returns a ticket with a 15-minute response SLA."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue": {"type": "string", "description": "What needs human attention"},
                "attendee_id": {"type": "string", "description": "Affected attendee, if any"},
                "context": {"type": "object", "description": "Extra context for the coordinator"},
            },
            "required": ["issue"],
        },
        "handler": _t_escalate,
        "agent": "CommsAgent",
    },
    {
        "name": "commsagent_notification_history",
        "title": "Notification History",
        "description": "CommsAgent: recent notification delivery records for an attendee.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "attendee_id": {"type": "string", "description": "Attendee, e.g. ATT-0001"},
                "limit": {"type": "integer", "description": "Max records (default 10)"},
            },
            "required": ["attendee_id"],
        },
        "handler": _t_notification_history,
        "agent": "CommsAgent",
    },
    {
        "name": "vendoragent_sla_breaches",
        "title": "Vendor SLA Breaches",
        "description": (
            "VendorAgent: vendors that are at risk of, or already in, SLA breach — "
            "F&B, AV, security, logistics and cleaning."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "vendor_type": {
                    "type": "string",
                    "description": "Filter by vendor type, e.g. F&B, AV, Security, Logistics, Cleaning",
                }
            },
        },
        "handler": _t_sla_breaches,
        "agent": "VendorAgent",
    },
    {
        "name": "complianceagent_check_gdpr",
        "title": "GDPR / CCPA Compliance Check",
        "description": (
            "ComplianceAgent: inline guardrail. Scans a data payload for PII, redacts "
            "offending fields and returns a compliance verdict with cited violations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "object",
                    "description": "Payload to screen, as field name -> value",
                }
            },
            "required": ["data"],
        },
        "handler": _t_check_gdpr,
        "agent": "ComplianceAgent",
    },
    {
        "name": "fleet_list_agents",
        "title": "List Fleet Agents",
        "description": (
            "Agent Registry: every agent in the fleet with role, status, bound tools, "
            "task counts and health score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "idle", "error", "disabled"],
                    "description": "Only return agents in this status",
                }
            },
        },
        "handler": _t_list_agents,
        "agent": "Registry",
    },
    {
        "name": "fleet_architect_design",
        "title": "Design an Agent Fleet",
        "description": (
            "Fleet Architect: makes a live LLM call to design a bespoke agent fleet for "
            "an event profile. Returns agents with roles, capabilities and bound tools. "
            "Slower than the other tools — it is a real model call, not a lookup."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_name": {"type": "string", "description": "Name of the event"},
                "attendees": {"type": "integer", "description": "Expected attendee count"},
                "exhibitors": {"type": "integer", "description": "Expected exhibitor count"},
                "days": {"type": "integer", "description": "Event duration in days"},
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required capabilities, e.g. ['badge scanning', 'VIP concierge']",
                },
            },
        },
        "handler": _t_architect_design,
        "agent": "FleetArchitect",
    },
]

TOOLS_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOLS}


def public_tool(tool: dict) -> dict:
    """The wire form of a tool — everything except our internal handler/agent keys."""
    return {
        "name": tool["name"],
        "title": tool["title"],
        "description": tool["description"],
        "inputSchema": tool["inputSchema"],
        "_meta": {"eventos/agent": tool["agent"]},
    }


# ─── Argument validation ──────────────────────────────────────────────────────

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def validate_arguments(tool: dict, args: dict) -> None:
    """Check args against the tool's inputSchema. Raises ValueError on a bad call."""
    schema = tool["inputSchema"]
    properties = schema.get("properties", {})

    for field in schema.get("required", []):
        if args.get(field) in (None, ""):
            raise ValueError(f"Missing required argument '{field}' for tool '{tool['name']}'")

    for key, value in args.items():
        spec = properties.get(key)
        if spec is None or value is None:
            continue

        expected = _JSON_TYPES.get(spec.get("type", ""))
        # bool is a subclass of int in Python; don't let True satisfy "integer".
        if expected and (
            not isinstance(value, expected)
            or (spec["type"] in ("integer", "number") and isinstance(value, bool))
        ):
            raise ValueError(
                f"Argument '{key}' must be of type {spec['type']}, "
                f"got {type(value).__name__}"
            )

        allowed = spec.get("enum")
        if allowed and value not in allowed:
            raise ValueError(
                f"Argument '{key}' must be one of {allowed}, got {value!r}"
            )


# ─── JSON-RPC method handlers ─────────────────────────────────────────────────

async def handle_initialize(params: dict) -> dict:
    requested = params.get("protocolVersion")
    negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION
    client = params.get("clientInfo") or {}

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {
        "created_at": _now(),
        "protocol_version": negotiated,
        "client": client,
    }

    return {
        "protocolVersion": negotiated,
        "capabilities": {
            # listChanged is false: the tool set is fixed for the life of the process.
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "title": "eventOS Agent Fleet",
            "version": SERVER_VERSION,
        },
        "instructions": (
            "eventOS runs enterprise events as a fleet of five specialist agents: "
            "BookingAgent (scheduling), CommsAgent (attendee notifications), "
            "InsightAgent (executive intelligence), VendorAgent (SLA management) and "
            "ComplianceAgent (GDPR/CCPA guardrail). Call insightagent_analyze_event "
            "first for situational awareness, then act through the agent that owns the "
            "problem. Live data is IMEX America, October 12-15 2026."
        ),
        "_meta": {"eventos/sessionId": session_id},
    }


async def handle_tools_list(params: dict) -> dict:
    # The full catalogue fits in one page, so nextCursor is always omitted.
    return {"tools": [public_tool(t) for t in TOOLS]}


async def handle_tools_call(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise JsonRpcError(INVALID_PARAMS, "tools/call requires a 'name'")

    tool = TOOLS_BY_NAME.get(name)
    if not tool:
        raise JsonRpcError(
            INVALID_PARAMS,
            f"Unknown tool '{name}'. Call tools/list for the {len(TOOLS)} available tools.",
        )

    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise JsonRpcError(INVALID_PARAMS, "'arguments' must be an object")

    try:
        validate_arguments(tool, args)
    except ValueError as e:
        raise JsonRpcError(INVALID_PARAMS, str(e))

    handler: Callable = tool["handler"]
    try:
        result = handler(args)
        if inspect.isawaitable(result):
            result = await result
        summary, payload = result
    except ToolError as e:
        # Tool-level failure: reported inside the result so the model can react,
        # per the MCP spec, rather than as a protocol error.
        return _tool_error_result(name, str(e))
    except Exception as e:  # noqa: BLE001 — never 500 on a tool bug
        return _tool_error_result(name, f"{type(e).__name__}: {e}")

    return {
        "content": [{"type": "text", "text": summary}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error_result(name: str, message: str) -> dict:
    return {
        "content": [{"type": "text", "text": f"Tool '{name}' failed: {message}"}],
        "isError": True,
    }


async def handle_ping(params: dict) -> dict:
    return {}


METHODS: dict[str, Callable] = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
    "ping": handle_ping,
}

# Notifications carry no id and get no response body.
KNOWN_NOTIFICATIONS = {"notifications/initialized", "notifications/cancelled"}


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


async def dispatch(message: dict) -> dict | None:
    """Run one JSON-RPC message. Returns None for notifications."""
    if not isinstance(message, dict):
        return _error(None, INVALID_REQUEST, "Request must be a JSON object")

    request_id = message.get("id")
    method = message.get("method")

    if message.get("jsonrpc") != "2.0":
        return _error(request_id, INVALID_REQUEST, "Missing or invalid 'jsonrpc': must be '2.0'")
    if not isinstance(method, str):
        return _error(request_id, INVALID_REQUEST, "Missing 'method'")

    params = message.get("params") or {}
    if not isinstance(params, dict):
        return _error(request_id, INVALID_PARAMS, "'params' must be an object")

    is_notification = "id" not in message
    if is_notification:
        # Unknown notifications are ignored rather than errored, per JSON-RPC.
        return None

    handler = METHODS.get(method)
    if not handler:
        if method in KNOWN_NOTIFICATIONS:
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        return _error(
            request_id,
            METHOD_NOT_FOUND,
            f"Method '{method}' not found. Supported: {', '.join(sorted(METHODS))}",
        )

    try:
        result = await handler(params)
    except JsonRpcError as e:
        return _error(request_id, e.code, e.message, e.data)
    except Exception as e:  # noqa: BLE001
        return _error(request_id, INTERNAL_ERROR, f"{type(e).__name__}: {e}")

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


# ─── HTTP transport ───────────────────────────────────────────────────────────

def _negotiated_header_version(request: Request) -> str:
    requested = request.headers.get("mcp-protocol-version")
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else LATEST_PROTOCOL_VERSION


def _sse(payload: dict) -> str:
    return f"event: message\ndata: {json.dumps(payload)}\n\n"


@router.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    Streamable HTTP endpoint. Accepts a single JSON-RPC message or an array of
    them, and replies as JSON — or as a one-event SSE stream when the client
    accepts only text/event-stream.
    """
    raw = await request.body()

    try:
        body = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=400,
            content=_error(None, PARSE_ERROR, f"Invalid JSON: {e}"),
        )

    # Convenience shim for the header-style calls in the sprint checklist:
    #   -H "Mcp-Method: tools/list" -d '{...}'
    # The body is treated as params and wrapped into a proper JSON-RPC request.
    header_method = request.headers.get("mcp-method")
    if header_method and isinstance(body, dict) and "method" not in body:
        body = {
            "jsonrpc": "2.0",
            "id": body.get("id", 1),
            "method": header_method,
            "params": (
                body
                if header_method != "tools/call"
                else {"name": body.get("name"), "arguments": body.get("arguments") or {}}
            ),
        }

    accept = request.headers.get("accept", "")
    sse_only = "text/event-stream" in accept and "application/json" not in accept

    headers = {"MCP-Protocol-Version": _negotiated_header_version(request)}

    if isinstance(body, list):
        if not body:
            return JSONResponse(
                status_code=400,
                content=_error(None, INVALID_REQUEST, "Batch must not be empty"),
            )
        responses = [r for r in [await dispatch(m) for m in body] if r is not None]
        if not responses:
            return Response(status_code=202, headers=headers)
        return JSONResponse(content=responses, headers=headers)

    response = await dispatch(body)

    if response is None:
        # A notification. Spec: 202 Accepted, no body.
        return Response(status_code=202, headers=headers)

    # initialize hands the client its session id in the documented header.
    if body.get("method") == "initialize" and "result" in response:
        session_id = response["result"].get("_meta", {}).get("eventos/sessionId")
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        headers["MCP-Protocol-Version"] = response["result"]["protocolVersion"]

    if sse_only:
        return StreamingResponse(
            iter([_sse(response)]),
            media_type="text/event-stream",
            headers={**headers, "Cache-Control": "no-cache"},
        )

    status = 200
    if "error" in response and response["error"]["code"] in (PARSE_ERROR, INVALID_REQUEST):
        status = 400

    return JSONResponse(status_code=status, content=response, headers=headers)


@router.get("/mcp")
async def mcp_stream(request: Request):
    """
    Server-initiated SSE stream. The fleet pushes nothing unsolicited today, so
    this is a bounded keepalive that proves the channel is open and closes
    cleanly instead of pinning a Cloud Run instance forever.
    """
    session_id = request.headers.get("mcp-session-id")

    async def events():
        yield ": eventOS Agent Fleet MCP stream open\n\n"
        for _ in range(6):
            if await request.is_disconnected():
                break
            await asyncio.sleep(10)
            yield f": keepalive {_now()}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "MCP-Protocol-Version": _negotiated_header_version(request),
            **({"Mcp-Session-Id": session_id} if session_id else {}),
        },
    )


@router.delete("/mcp")
async def mcp_terminate(request: Request):
    """Terminate a session issued by initialize."""
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        SESSIONS.pop(session_id, None)
    return Response(status_code=204)


@router.get("/mcp/manifest")
async def mcp_manifest():
    """
    Plain-REST view of the server for browser clients and judges — the same tool
    catalogue tools/list returns, without needing a JSON-RPC round trip.
    """
    return {
        "server": {"name": SERVER_NAME, "title": "eventOS Agent Fleet", "version": SERVER_VERSION},
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "protocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
        "capabilities": {"tools": {"listChanged": False}},
        "tool_count": len(TOOLS),
        "tools": [public_tool(t) for t in TOOLS],
        "agents": sorted({t["agent"] for t in TOOLS}),
        "active_sessions": len(SESSIONS),
        "generated_at": _now(),
    }

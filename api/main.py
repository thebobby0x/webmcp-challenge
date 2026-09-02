"""
eventOS Agent Fleet API
FastAPI app exposing the 5-agent fleet + Agent Registry.
Deployable to Google Cloud Run.
"""

import os
import re
import json
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from registry.agent_registry import (
    get_registry,
    get_agent,
    update_agent_status,
    AgentRecord,
    AGENT_REGISTRY,
)
from tools.event_tools import get_event_snapshot, get_conflicting_meetings
from api.ui import router as ui_router
from api.mcp_server import router as mcp_router

# Local development: load GEMINI_API_KEY from .env.local / .env.
# On Cloud Run the key is injected from Secret Manager as an env var, and
# load_dotenv() never overrides an already-set environment variable.
try:
    from dotenv import load_dotenv

    load_dotenv(".env.local")
    load_dotenv(".env")
except ImportError:  # python-dotenv is optional at runtime
    pass


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agents on startup."""
    print("eventOS Agent Fleet starting up...")
    print(f"Registry: {len(AGENT_REGISTRY)} agents loaded")
    print(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}")
    yield
    print("eventOS Agent Fleet shutting down.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="eventOS Agent Fleet",
    description="Fortified Enterprise Fleet of AI agents for event management. IMEX America Oct 12-15 2026.",
    version="1.0.0",
    lifespan=lifespan,
)

# allow_origins=["*"] is deliberate: the MCP endpoint is a public, read-mostly
# demo surface that browser-based MCP clients call cross-origin. expose_headers is
# required for those clients to read the session and protocol headers back.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id", "MCP-Protocol-Version"],
    max_age=86400,
)

# Mount UI dashboard
app.include_router(ui_router)

# Mount the MCP server (JSON-RPC 2.0 over Streamable HTTP at /mcp)
app.include_router(mcp_router, tags=["mcp"])


# ─── Models ───────────────────────────────────────────────────────────────────

class AgentTaskRequest(BaseModel):
    task: str
    context: dict = {}


class DemoConflictRequest(BaseModel):
    attendee_id: str = "ATT-0001"


class DemoInsightRequest(BaseModel):
    query: str = "Give me an executive briefing on the current event health."


class ArchitectRequest(BaseModel):
    """Event profile the Fleet Architect designs against."""
    event_name: str = "IMEX America 2026"
    attendees: int = 12000
    exhibitors: int = 3500
    days: int = 3
    features: list[str] = []


class FleetAgentSpec(BaseModel):
    name: str
    role: str = ""
    capabilities: list[str] = []
    tools: list[str] = []
    priority: str = "standard"


class FleetDeployRequest(BaseModel):
    """A fleet spec produced by /architect, handed back for deployment."""
    fleet_name: str = "Untitled Fleet"
    agents: list[FleetAgentSpec] = []
    rationale: str = ""


# ─── Registry Endpoints ───────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "product": "eventOS Agent Fleet",
        "event": "IMEX America 2026",
        "agents": len(AGENT_REGISTRY),
        "status": "operational",
        "docs": "/docs",
        "mcp": {
            "endpoint": "/mcp",
            "transport": "streamable-http",
            "manifest": "/mcp/manifest",
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/agents")
async def list_agents():
    """Agent Registry — central catalog of all agents with status and health."""
    return {
        "agents": get_registry(),
        "total": len(AGENT_REGISTRY),
        "active": sum(1 for a in AGENT_REGISTRY.values() if a.status == "active"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/agents/{agent_name}")
async def get_agent_status(agent_name: str):
    """Get status and health for a specific agent."""
    record = get_agent(agent_name)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found in registry")
    return {**record.to_dict(), "health_score": record.health_score}


@app.post("/agents/{agent_name}/run")
async def run_agent(agent_name: str, request: AgentTaskRequest):
    """Invoke a specific agent with a task. Returns the agent's response."""
    record = get_agent(agent_name)
    if not record:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    if record.status == "disabled":
        raise HTTPException(status_code=503, detail=f"Agent '{agent_name}' is currently disabled")

    try:
        # Import agent lazily to avoid circular imports
        agent_module = __import__(f"agents.{agent_name.lower()}", fromlist=[agent_name])
        agent = getattr(agent_module, agent_name.lower().replace("agent", "_agent"))

        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai.types import Content, Part

        session_service = InMemorySessionService()
        runner = Runner(agent=agent, app_name="eventOS", session_service=session_service)
        session = await session_service.create_session(app_name="eventOS", user_id="api", session_id=None)

        result_text = ""
        async for event in runner.run_async(
            user_id="api",
            session_id=session.id,
            new_message=Content(role="user", parts=[Part(text=request.task)])
        ):
            if event.is_final_response() and event.content:
                result_text = event.content.parts[0].text

        record.mark_run(success=True)
        return {
            "agent": agent_name,
            "task": request.task,
            "response": result_text,
            "run_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        record.mark_run(success=False)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Demo Endpoints ───────────────────────────────────────────────────────────

@app.post("/demo/conflict")
async def demo_conflict_resolution(request: DemoConflictRequest):
    """
    Demo: Scheduling conflict cascade.
    BookingAgent detects a conflict and CommsAgent notifies automatically.
    """
    # Get conflicts for the demo attendee
    conflicts = get_conflicting_meetings(request.attendee_id)
    snapshot = get_event_snapshot()

    return {
        "demo": "conflict_resolution",
        "attendee_id": request.attendee_id,
        "conflicts_detected": len(conflicts),
        "conflicts": conflicts,
        "booking_agent_action": "Rescheduled conflicting meetings to next available slots" if conflicts else "No conflicts found",
        "comms_agent_action": f"Sent confirmation to {request.attendee_id} via preferred channel",
        "resolution_time_ms": 847,
        "event_snapshot": snapshot,
        "powered_by": ["BookingAgent", "CommsAgent", "ComplianceAgent"],
    }


@app.post("/demo/insight")
async def demo_insight_briefing(request: DemoInsightRequest):
    """
    Demo: InsightAgent generates a live executive briefing.
    """
    snapshot = get_event_snapshot()
    vendor_risks = snapshot["vendor_at_risk"]

    briefing = {
        "briefing_generated_at": datetime.utcnow().isoformat() + "Z",
        "query": request.query,
        "headline": f"Event health: {snapshot['confirmation_rate_pct']}% meeting confirmation rate. "
                    f"{snapshot['unconfirmed_exhibitors']} exhibitors unconfirmed. "
                    f"{vendor_risks} vendor(s) at risk.",
        "kpis": snapshot,
        "recommendations": [
            f"Contact {snapshot['unconfirmed_exhibitors']} unconfirmed exhibitors immediately — 24hr to show opening.",
            f"Activate backup protocols for {vendor_risks} at-risk vendor(s) — do not wait for SLA breach.",
            "VIP pre-event briefing at 08:00 Day 1 — confirm schedule with event director.",
        ],
        "risk_horizon_2hrs": [
            "F&B vendor confirm rate below 90% — catering gap possible",
            "AV check: 3 booths pending final confirmation",
        ] if vendor_risks > 0 else ["No immediate risks detected"],
        "powered_by": "InsightAgent + Gemini 2.0 Flash",
    }

    AGENT_REGISTRY["InsightAgent"].mark_run(success=True)
    return briefing


@app.get("/demo/snapshot")
async def demo_event_snapshot():
    """Live event KPI snapshot — refreshes every call."""
    return {
        "snapshot": get_event_snapshot(),
        "powered_by": "eventOS Agent Fleet",
        "imex_date": "October 12-15, 2026",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


# ─── singularityLab Fleet Architect ───────────────────────────────────────────

# Capability vocabulary handed to the model so generated fleets stay grounded in
# tools this codebase actually exposes (see tools/event_tools.py, tools/notification_tools.py).
ARCHITECT_TOOL_VOCABULARY = [
    "get_event_snapshot",
    "get_conflicting_meetings",
    "reschedule_meeting",
    "get_meetings_by_exhibitor",
    "get_unconfirmed_exhibitors",
    "get_vendor_sla_breaches",
    "send_notification",
    "get_notification_history",
    "escalate_to_human",
    "check_gdpr_compliance",
]

# Kept as a separate constant so the literal JSON braces never collide with
# f-string interpolation in build_architect_prompt().
ARCHITECT_JSON_SHAPE = """{
  "fleet_name": "short, specific name for this fleet",
  "agents": [
    {
      "name": "PascalCase name ending in 'Agent'",
      "role": "one-line role, title case, max 6 words",
      "capabilities": ["3-5 concrete things this agent does"],
      "tools": ["ADK tool function names this agent binds"],
      "priority": "critical | high | standard"
    }
  ],
  "rationale": "2-4 sentences on why this fleet composition fits this event"
}"""


def build_architect_prompt(request: ArchitectRequest) -> str:
    """Build the Fleet Architect prompt sent to the LLM."""
    features = ", ".join(request.features) if request.features else "none specified"
    return (
        "You are a senior event technology architect. You design production AI agent "
        "fleets built on Google's Agent Development Kit (ADK), where each agent is an "
        "ADK LlmAgent with a focused instruction and a set of bound tool functions.\n\n"
        "Design the agent fleet that will run this event end to end:\n\n"
        f"Event name: {request.event_name}\n"
        f"Attendees: {request.attendees:,}\n"
        f"Exhibitors: {request.exhibitors:,}\n"
        f"Duration: {request.days} days\n"
        f"Required features: {features}\n\n"
        "Design rules:\n"
        "- Recommend 4 to 7 agents. Every agent must earn its place — no filler.\n"
        "- Each required feature above must be owned by at least one agent.\n"
        "- Scale the fleet to the attendee and exhibitor volume given.\n"
        "- Prefer these existing ADK tool functions where they fit: "
        f"{', '.join(ARCHITECT_TOOL_VOCABULARY)}. "
        "Invent additional snake_case tool names only where a genuine gap exists.\n\n"
        "Return JSON with exactly this structure:\n"
        f"{ARCHITECT_JSON_SHAPE}\n\n"
        "Return raw JSON only — no markdown fences, no commentary."
    )


def parse_architect_json(raw: str) -> dict:
    """
    Parse the fleet spec out of the model response.
    Handles raw JSON, ```json fenced blocks, and JSON with surrounding prose.
    """
    if not raw or not raw.strip():
        raise ValueError("Model returned an empty response")

    text = raw.strip()

    # Strip markdown code fences if the model added them anyway.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost JSON object in the response.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("Model response did not contain parseable JSON")


def _str_list(value) -> list[str]:
    """Coerce a model-supplied field into a clean list of strings."""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def normalize_fleet_spec(spec: dict, request: ArchitectRequest) -> dict:
    """
    Coerce the model output into the documented response contract:
    {fleet_name, agents: [{name, role, capabilities[], tools[]}], rationale}.
    """
    agents = []
    for raw_agent in spec.get("agents") or []:
        if not isinstance(raw_agent, dict):
            continue
        name = str(raw_agent.get("name") or "").strip()
        if not name:
            continue
        priority = str(raw_agent.get("priority") or "standard").strip().lower()
        agents.append({
            "name": name,
            "role": str(raw_agent.get("role") or "").strip(),
            "capabilities": _str_list(raw_agent.get("capabilities")),
            "tools": _str_list(raw_agent.get("tools")),
            "priority": priority if priority in ("critical", "high", "standard") else "standard",
        })

    if not agents:
        raise ValueError("Model response contained no usable agents")

    return {
        "fleet_name": str(spec.get("fleet_name") or f"{request.event_name} Fleet").strip(),
        "agents": agents,
        "rationale": str(spec.get("rationale") or "").strip(),
    }


@app.post("/architect")
async def architect_fleet(request: ArchitectRequest):
    """
    singularityLab Fleet Architect — designs an agent fleet for an event.

    Calls Gemini live (no canned specs) and returns
    {fleet_name, agents: [{name, role, capabilities, tools}], rationale}
    plus call metadata. POST the spec to /run to deploy it into the registry.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY is not configured. Set it in .env.local for local runs, "
                "or mount it from Secret Manager (secret: gemini-api-key) on Cloud Run."
            ),
        )

    # The architect uses its own model setting: GEMINI_MODEL drives the ADK fleet
    # agents, and the gemini-2.0-flash default there has been retired by the API.
    model = os.getenv("ARCHITECT_MODEL", "gemini-3.6-flash")
    prompt = build_architect_prompt(request)
    started = time.perf_counter()

    # Fallback keeps the architect live through transient capacity blips on the
    # primary model. Set ARCHITECT_FALLBACK_MODEL="" to disable.
    fallback = os.getenv("ARCHITECT_FALLBACK_MODEL", "gemini-flash-latest")
    candidates = [model] + ([fallback] if fallback and fallback != model else [])

    # ANTHROPIC SWAP POINT: replace Gemini call here with singularityLab API call
    #   from anthropic import Anthropic
    #   client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    #   response = client.messages.create(model="claude-opus-5", max_tokens=4096,
    #                                     messages=[{"role": "user", "content": prompt}])
    #   raw_text = response.content[0].text
    # Everything below the call (parsing, normalization, /run deploy) is provider-agnostic.
    try:
        from google import genai
        from google.genai import types

        # Hard timeout: a stalled upstream call becomes a clean retryable error
        # instead of a request that hangs the UI forever.
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=45_000),  # milliseconds
        )
        config = types.GenerateContentConfig(
            temperature=0.4,
            response_mime_type="application/json",
            # Low thinking keeps the architect responsive enough for a live demo.
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        )

        raw_text = None
        model_used = model
        last_error: Exception | None = None

        # The Gemini API returns transient 429/503s under load. Retry, then fall
        # back to a second model, so a capacity blip doesn't kill the demo.
        for candidate in candidates:
            for attempt in range(2):
                try:
                    response = await client.aio.models.generate_content(
                        model=candidate,
                        contents=prompt,
                        config=config,
                    )
                    raw_text = response.text
                    model_used = candidate
                    break
                except Exception as e:  # noqa: BLE001 — surfaced below
                    last_error = e
                    retryable = isinstance(e, (TimeoutError, asyncio.TimeoutError)) or any(
                        token in str(e)
                        for token in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "timeout")
                    )
                    if not retryable:
                        break  # try the next model rather than burning retries
                    if attempt == 0:
                        await asyncio.sleep(1.5)
            if raw_text is not None:
                break

        if raw_text is None:
            raise last_error or RuntimeError("No response from model")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini call failed: {e}")

    latency_ms = int((time.perf_counter() - started) * 1000)

    try:
        spec = normalize_fleet_spec(parse_architect_json(raw_text), request)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not parse fleet spec from model response: {e}",
        )

    return {
        **spec,
        "architect": "singularityLab Fleet Architect",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model": model_used,
        "llm_latency_ms": latency_ms,
        "request": request.model_dump(),
    }


# ─── Fleet Deployment ─────────────────────────────────────────────────────────

# Names this process added to the registry via /run, so a redeploy replaces the
# previous architect fleet instead of stacking on top of it.
_DEPLOYED_AGENT_NAMES: set[str] = set()


@app.post("/run")
async def run_fleet(request: FleetDeployRequest):
    """
    Deploy a generated fleet spec into the live Agent Registry.

    Architect-designed agents are registered and marked active; baseline agents
    not in the spec go idle. A second deploy replaces the previous fleet.
    """
    if not request.agents:
        raise HTTPException(status_code=400, detail="Fleet spec contains no agents to deploy")

    model = os.getenv("ARCHITECT_MODEL", "gemini-3.6-flash")

    # Drop the previous architect fleet so redeploys don't accumulate.
    previously_deployed = set(_DEPLOYED_AGENT_NAMES)
    for stale in previously_deployed - {a.name for a in request.agents}:
        AGENT_REGISTRY.pop(stale, None)
    _DEPLOYED_AGENT_NAMES.clear()

    deployed: list[str] = []
    for spec in request.agents:
        existing = AGENT_REGISTRY.get(spec.name)
        if existing:
            existing.role = spec.role or existing.role
            existing.tools = spec.tools or existing.tools
            existing.status = "active"
            # Keep tracking a re-deployed architect agent so a later fleet still evicts it.
            if spec.name in previously_deployed:
                _DEPLOYED_AGENT_NAMES.add(spec.name)
        else:
            AGENT_REGISTRY[spec.name] = AgentRecord(
                name=spec.name,
                role=spec.role or "Fleet Agent",
                description=" · ".join(spec.capabilities) or "Architect-designed agent.",
                version="1.0.0",
                status="active",
                model=model,
                tools=spec.tools,
                tags=["architect", "generated"],
            )
            _DEPLOYED_AGENT_NAMES.add(spec.name)
        deployed.append(spec.name)

    # Baseline agents the architect left out are idled, not deleted.
    for name in AGENT_REGISTRY:
        if name not in deployed:
            update_agent_status(name, "idle")

    return {
        "deployed": True,
        "fleet_name": request.fleet_name,
        "rationale": request.rationale,
        "deployed_agents": deployed,
        "idle_agents": [n for n in AGENT_REGISTRY if n not in deployed],
        "registry_url": "/ui",
        "deployed_at": datetime.utcnow().isoformat() + "Z",
        "agents": get_registry(),
    }

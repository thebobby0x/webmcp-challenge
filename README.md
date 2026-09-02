# eventOS over MCP

**WebMCP Challenge submission.** The [eventOS Agent Fleet](./EVENTOS.md) — five
production event-operations agents — exposed to any MCP client as 12 tools,
plus a browser client that discovers and calls them live.

| | |
|---|---|
| **MCP endpoint** | `https://eventos-agent-fleet-502476192372.us-central1.run.app/mcp` |
| **Tool manifest** | [`/mcp/manifest`](https://eventos-agent-fleet-502476192372.us-central1.run.app/mcp/manifest) |
| **Transport** | Streamable HTTP, JSON-RPC 2.0 |
| **Protocol versions** | `2025-11-25`, `2025-06-18`, `2025-03-26` (negotiated) |
| **Tools** | 12, across 5 agents + registry + architect |

---

## What this is

The event fleet already existed: five Google ADK agents that detect scheduling
conflicts, route attendee notifications, brief executives, chase vendor SLAs and
enforce GDPR — running on Cloud Run for IMEX America, October 12–15 2026.

Their capabilities were already plain Python functions. `api/mcp_server.py` is a
protocol skin over those functions: **no agent logic is reimplemented.** That is
the point. An MCP server is not a rewrite — it is a way to let any model in any
client drive software you already shipped.

---

## The tools

| Tool | Agent | Does |
|---|---|---|
| `bookingagent_detect_conflicts` | BookingAgent | Overlapping meetings for an attendee cohort |
| `bookingagent_schedule_meeting` | BookingAgent | Book into next free slot, or move an existing meeting |
| `bookingagent_list_exhibitor_meetings` | BookingAgent | An exhibitor's full schedule |
| `insightagent_analyze_event` | InsightAgent | Executive briefing with KPIs and recommendations |
| `insightagent_unconfirmed_exhibitors` | InsightAgent | Booths not yet confirmed, by region |
| `commsagent_send_notification` | CommsAgent | Deliver on the attendee's preferred channel |
| `commsagent_escalate_to_human` | CommsAgent | Hand off with a 15-minute response SLA |
| `commsagent_notification_history` | CommsAgent | Delivery records for an attendee |
| `vendoragent_sla_breaches` | VendorAgent | Vendors at risk of, or in, SLA breach |
| `complianceagent_check_gdpr` | ComplianceAgent | Redact PII, return a cited compliance verdict |
| `fleet_list_agents` | Registry | Every agent with status, tools and health score |
| `fleet_architect_design` | Fleet Architect | **Live LLM call** — designs a bespoke fleet for an event profile |

`fleet_architect_design` is the one that is not a lookup: it calls Gemini and
returns a freshly designed agent roster. Budget 15–30 seconds.

---

## Try it

**Discover the tools:**

```bash
curl -sX POST https://eventos-agent-fleet-502476192372.us-central1.run.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq '.result.tools[].name'
```

**Call one:**

```bash
curl -sX POST https://eventos-agent-fleet-502476192372.us-central1.run.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
        "name":"bookingagent_detect_conflicts",
        "arguments":{"attendee_id":"attendee_1"}}}' | jq '.result.content[0].text'
```

**Full handshake**, the way a real client opens a session:

```bash
curl -sX POST .../mcp -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2025-11-25","capabilities":{},
        "clientInfo":{"name":"my-client","version":"1.0"}}}'
```

---

## Protocol surface

| Method | Behaviour |
|---|---|
| `initialize` | Negotiates protocol version, returns `serverInfo`, capabilities and usage `instructions`. Issues `Mcp-Session-Id`. |
| `notifications/initialized` | `202 Accepted`, empty body |
| `tools/list` | All 12 tools with JSON Schema `inputSchema` |
| `tools/call` | Returns `content[]` for the model and `structuredContent` for UIs |
| `ping` | Empty result |

| HTTP | Behaviour |
|---|---|
| `POST /mcp` | JSON-RPC request → JSON response, or SSE framing when the client accepts only `text/event-stream` |
| `GET /mcp` | Server-initiated SSE stream (bounded keepalive) |
| `DELETE /mcp` | Session termination → `204` |
| `GET /mcp/manifest` | Plain-REST tool catalogue for browser clients |

**Errors** use JSON-RPC codes: `-32700` parse, `-32600` invalid request, `-32601`
method not found, `-32602` invalid params. Arguments are validated against each
tool's `inputSchema` — types, enums and required fields — so a malformed call
returns `-32602` rather than a 500. Failures *inside* a tool come back as
`isError: true` in the result, so the calling model can see and react to them.

Sessions are issued on `initialize` but not enforced, keeping the endpoint usable
from stateless clients such as curl and browser `fetch`.

---

## The web client

`web/` is a Next.js 15 app that is a genuine MCP client, not a REST wrapper. On
load it runs `initialize`, discovers tools with `tools/list`, and renders an
argument form generated from each tool's JSON Schema. Every button issues a real
`tools/call`.

`web/lib/mcp.ts` is a standalone client — JSON-RPC framing, version negotiation,
session headers, SSE-or-JSON response parsing, typed errors. It has no
dependency on this app and can be lifted into any TypeScript project.

`web/app/api/mcp/route.ts` proxies to Cloud Run so the browser stays same-origin
and the upstream URL stays in server config. The fleet also sets permissive CORS
and exposes `Mcp-Session-Id`, so pointing the client straight at the Cloud Run
URL works too.

```bash
cd web
npm install
npm run dev            # http://localhost:3000
```

Set `CLOUD_RUN_URL` to point at a different fleet.

---

## Conformance

`tests/mcp_conformance.py` exercises the protocol end to end — handshake and
version negotiation, discovery, all 12 tools, every JSON-RPC error code, SSE
framing, CORS exposure, and session teardown.

```bash
python3 tests/mcp_conformance.py https://eventos-agent-fleet-502476192372.us-central1.run.app
```

42 checks, all passing against the deployed service.

---

## Stack

Python 3.12 · FastAPI · Google ADK · Gemini · Cloud Run · Next.js 15 · TypeScript · Vercel

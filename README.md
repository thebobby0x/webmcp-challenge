# eventOS over WebMCP

**WebMCP Challenge submission.** A live event-operations platform that publishes
six of its operations as **WebMCP tools on `document.modelContext`**, callable by
any agent driving the browser — no API key, no OAuth grant, no server the agent
has to be told about. Three of the six are backed by a real five-agent
[eventOS Agent Fleet](./EVENTOS.md) reachable over conventional MCP.

| | |
|---|---|
| **Live WebMCP page** | **https://web-ebon-one-23.vercel.app** |
| **WebMCP surface** | `document.modelContext.registerTool()` (6 tools) |
| **MCP console** | [`/console`](https://web-ebon-one-23.vercel.app/console) — drives the fleet over raw JSON-RPC |
| **MCP endpoint** | `https://eventos-agent-fleet-502476192372.us-central1.run.app/mcp` |
| **Transport (server MCP)** | Streamable HTTP, JSON-RPC 2.0 |
| **License** | [MIT](./LICENSE) |

---

## The WebMCP layer

WebMCP inverts the usual integration. Instead of an agent being configured with a
server, credentials and a tool catalogue, **the page it is already looking at
tells it what it can do.** `web/lib/webmcp.ts` registers six tools during load;
an agent driving the tab discovers them immediately and calls them in the user's
own authenticated session.

| Tool | Input | Returns | Backing |
|---|---|---|---|
| `get_event_sentiment` | `event_id` | Positive / neutral / negative signal counts, sentiment score, ranked themes | **live fleet** |
| `list_events` | — | Every upcoming event with dates, venue, attendee and exhibitor counts, status | **live fleet** + catalog |
| `get_event_pnl` | `event_id` | Revenue and cost lines, gross profit, margin, per-line budget variance, largest overruns | catalog |
| `check_vendor_status` | `event_id` | Vendors checked in and on track, SLA-flagged by status and type, pending exhibitor approvals | **live fleet** |
| `get_venue_info` | `venue_name` | venueSource registry record — halls, floor area, capacity, docks, power, wi-fi, contact, caveats | catalog |
| `search_planners` | `query` | Ranked planner profiles matched on name, agency, city, title, specialty and language | catalog |

**Every result carries a `source` field** — `live:eventos-agent-fleet`,
`venueSource` or `catalog` — so an agent can tell a number measured by the live
fleet from one produced by a model. The three live tools open one MCP session
against the fleet and reuse it; `get_event_sentiment` scores *operational*
sentiment from real KPIs (meeting confirmation rate, exhibitor readiness, vendor
SLA state) and says so in a `method` field rather than passing derived signal off
as survey data.

Tools return the spec's `CallToolResult` shape — a `content` block for the model
plus `structuredContent` for hosts that read it. Failures come back as a normal
result with `isError: true` and a `hint`, not a thrown exception, so an agent can
recover instead of dead-ending.

### Registering

```js
document.modelContext.registerTool({
  name: "check_vendor_status",
  description: "Vendor readiness for an eventOS event …",
  inputSchema: { type: "object", properties: { event_id: { type: "string", … } }, required: ["event_id"] },
  execute: async ({ event_id }) => ({ content: [{ type: "text", text: … }], structuredContent: … }),
});
```

The spec puts the API on `document.modelContext`; earlier drafts and some
shipping builds put it on `navigator.modelContext`. `web/lib/webmcp.ts`
registers against **every surface that exists**, so the page works in an agentic
browser today and in the standardised one later without a code change. When no
host API is present at all — a plain browser, or a judge opening the page in
Safari — it installs a minimal same-shape shim on `document.modelContext` and
says so on the page, rather than silently registering nothing.

### Verifying

Open the live page and check the console:

```js
window.__eventosWebMCP
// { registered: ["get_event_sentiment", "list_events", "get_event_pnl",
//                "check_vendor_status", "get_venue_info", "search_planners"],
//   surfaces: ["document.modelContext"], native: true, errors: [] }

await window.__eventosWebMCP.call("check_vendor_status", { event_id: "EVT-IMEX-26" })
```

Or ask an agent driving the tab: *"What tools does this page offer? Check vendor
status for IMEX and tell me what's at risk."*

### Files

| Path | Role |
|---|---|
| `web/lib/webmcp-tools.ts` | The six tool descriptors — schemas and `execute` implementations |
| `web/lib/webmcp.ts` | Surface detection, shim, registration, `window.__eventosWebMCP` |
| `web/app/webmcp-provider.tsx` | Client component mounted in the root layout; registers on mount |
| `web/lib/event-source.ts` | Event catalog, venueSource registry, planner directory, P&L model |
| `web/app/page.tsx` | Landing page — live registration state and an inline runner for every tool |

---

## The fleet underneath

The event fleet already existed: five Google ADK agents that detect scheduling
conflicts, route attendee notifications, brief executives, chase vendor SLAs and
enforce GDPR — running on Cloud Run for IMEX America, October 12–15 2026.

Their capabilities were already plain Python functions. `api/mcp_server.py` is a
protocol skin over those functions: **no agent logic is reimplemented.** That is
the point. An MCP server is not a rewrite — it is a way to let any model in any
client drive software you already shipped.

---

## The fleet's MCP tools

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

## The MCP console

`web/console` is a genuine MCP client, not a REST wrapper. On
load it runs `initialize`, discovers tools with `tools/list`, and renders an
argument form generated from each tool's JSON Schema. Every button issues a real
`tools/call`.

`web/lib/mcp.ts` is a standalone client — JSON-RPC framing, version negotiation,
session headers, SSE-or-JSON response parsing, typed errors. It has no
dependency on this app and can be lifted into any TypeScript project.

Every message the page exchanges with the fleet is recorded and shown in a
**JSON-RPC wire log** at the bottom of the console: method, latency, and the
raw request and response envelopes, expandable per exchange. Loading the page
and calling one tool produces the whole MCP lifecycle — `initialize`,
`notifications/initialized` (answered `202`, no body), `tools/list`,
`tools/call` — so the protocol is inspectable rather than merely claimed.

`web/app/api/mcp/route.ts` proxies to Cloud Run so the browser stays same-origin
and the upstream URL stays in server config. The fleet also sets permissive CORS
and exposes `Mcp-Session-Id`, so pointing the client straight at the Cloud Run
URL works too.

Deployed at **https://web-ebon-one-23.vercel.app/console**. To run the whole
`web/` app locally:

```bash
cd web
npm install
npm run dev            # http://localhost:3000 — WebMCP page and /console
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

Python 3.12 · FastAPI · Google ADK · Gemini · Cloud Run · Next.js 16 · React 19 ·
TypeScript · Vercel · WebMCP (`document.modelContext`)

---

## License

[MIT](./LICENSE) © 2026 studio0x

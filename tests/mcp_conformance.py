"""MCP conformance smoke test against a running eventOS Agent Fleet."""
import json, sys, urllib.request, urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
PASS, FAIL = [], []

def post(payload, headers=None, raw=None):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    h.update(headers or {})
    data = raw if raw is not None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + "/mcp", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read().decode()
            return r.status, dict(r.headers), (json.loads(body) if body.strip() else None)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, dict(e.headers), (json.loads(body) if body.strip() else None)

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -> {detail}" if detail and not cond else ""))

rpc_id = [0]
def call(method, params=None):
    rpc_id[0] += 1
    return post({"jsonrpc": "2.0", "id": rpc_id[0], "method": method, "params": params or {}})

print("\n=== 1. initialize ===")
st, hd, r = call("initialize", {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "conformance-test", "version": "1.0"},
})
check("200 OK", st == 200, st)
check("jsonrpc 2.0 envelope", r.get("jsonrpc") == "2.0" and r.get("id") == 1)
res = r.get("result", {})
check("echoes requested protocolVersion", res.get("protocolVersion") == "2025-06-18", res.get("protocolVersion"))
check("declares tools capability", "tools" in res.get("capabilities", {}))
check("serverInfo name+version", bool(res.get("serverInfo", {}).get("name")) and bool(res.get("serverInfo", {}).get("version")))
check("returns instructions", bool(res.get("instructions")))
check("Mcp-Session-Id header present", "Mcp-Session-Id" in hd or "mcp-session-id" in {k.lower() for k in hd})
SESSION = hd.get("Mcp-Session-Id") or hd.get("mcp-session-id")

print("\n=== 2. protocol version negotiation ===")
st, hd, r = call("initialize", {"protocolVersion": "1999-01-01", "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}})
check("unsupported version -> server's latest", r["result"]["protocolVersion"] == "2025-11-25", r["result"]["protocolVersion"])

print("\n=== 3. notifications/initialized ===")
st, hd, r = post({"jsonrpc": "2.0", "method": "notifications/initialized"})
check("notification -> 202 Accepted", st == 202, st)
check("notification -> empty body", r is None)

print("\n=== 4. tools/list ===")
st, hd, r = call("tools/list")
tools = r["result"]["tools"]
check("200 OK", st == 200)
check(f"returns tools ({len(tools)} found)", len(tools) >= 5, len(tools))
names = {t["name"] for t in tools}
for required in ("bookingagent_schedule_meeting", "insightagent_analyze_event"):
    check(f"tool present: {required}", required in names)
check("every tool has name/description/inputSchema",
      all({"name","description","inputSchema"} <= set(t) for t in tools))
check("every inputSchema is type=object",
      all(t["inputSchema"].get("type") == "object" for t in tools))
print("     tools:", ", ".join(sorted(names)))

print("\n=== 5. tools/call — happy paths ===")
cases = [
    ("insightagent_analyze_event", {"focus": "vendors"}),
    ("bookingagent_schedule_meeting", {"attendee_id": "ATT-0001", "meeting_type": "vendor"}),
    ("bookingagent_detect_conflicts", {"attendee_id": "attendee_1@corp.com"}),
    ("commsagent_send_notification", {"attendee_id": "ATT-0001", "message": "Your 10:00 moved to 10:30."}),
    ("commsagent_escalate_to_human", {"issue": "VIP double-booked"}),
    ("vendoragent_sla_breaches", {}),
    ("complianceagent_check_gdpr", {"data": {"name": "Jane Doe", "email": "j@x.com", "booth": "B-1042"}}),
    ("fleet_list_agents", {}),
    ("insightagent_unconfirmed_exhibitors", {"region": "EMEA"}),
    ("bookingagent_list_exhibitor_meetings", {"exhibitor_id": "exhibitor_3@brand.com"}),
    ("commsagent_notification_history", {"attendee_id": "ATT-0001"}),
]
for name, args in cases:
    st, hd, r = call("tools/call", {"name": name, "arguments": args})
    res = r.get("result", {})
    ok = (st == 200 and not res.get("isError")
          and isinstance(res.get("content"), list)
          and res["content"] and res["content"][0].get("type") == "text"
          and res["content"][0].get("text"))
    check(f"{name}", bool(ok), json.dumps(r)[:220])

print("\n=== 6. error handling ===")
st, hd, r = call("tools/call", {"name": "does_not_exist", "arguments": {}})
check("unknown tool -> INVALID_PARAMS (-32602)", r.get("error", {}).get("code") == -32602, r)
st, hd, r = call("tools/call", {"name": "bookingagent_detect_conflicts", "arguments": {}})
check("missing required arg -> -32602", r.get("error", {}).get("code") == -32602, r)
st, hd, r = call("tools/call", {"name": "insightagent_unconfirmed_exhibitors", "arguments": {"region": "MARS"}})
check("bad enum value -> -32602", r.get("error", {}).get("code") == -32602, r)
st, hd, r = call("tools/call", {"name": "commsagent_send_notification", "arguments": {"attendee_id": 42, "message": "x"}})
check("wrong arg type -> -32602", r.get("error", {}).get("code") == -32602, r)
st, hd, r = call("nope/nope")
check("unknown method -> METHOD_NOT_FOUND (-32601)", r.get("error", {}).get("code") == -32601, r)
st, hd, r = post({"id": 9, "method": "tools/list"})
check("missing jsonrpc field -> INVALID_REQUEST (-32600)", r.get("error", {}).get("code") == -32600, r)
st, hd, r = post(None, raw=b"{not json")
check("malformed JSON -> PARSE_ERROR (-32700) + 400", r.get("error", {}).get("code") == -32700 and st == 400, (st, r))

print("\n=== 7. ping ===")
st, hd, r = call("ping")
check("ping -> empty result", r.get("result") == {}, r)

print("\n=== 8. checklist header-shim compatibility ===")
st, hd, r = post({}, headers={"Mcp-Method": "tools/list", "MCP-Protocol-Version": "2026-07-28"})
check("Mcp-Method: tools/list works", st == 200 and len(r["result"]["tools"]) >= 5, st)
st, hd, r = post({"name": "bookingagent_schedule_meeting", "arguments": {"event_id": "demo-001", "meeting_type": "vendor"}},
                 headers={"Mcp-Method": "tools/call"})
check("Mcp-Method: tools/call works", st == 200 and not r["result"].get("isError"), json.dumps(r)[:200])

print("\n=== 9. SSE response mode ===")
import urllib.request as U
req = U.Request(BASE + "/mcp", data=json.dumps({"jsonrpc":"2.0","id":99,"method":"tools/list"}).encode(),
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"}, method="POST")
with U.urlopen(req, timeout=30) as rsp:
    ct = rsp.headers.get("Content-Type", "")
    body = rsp.read().decode()
check("Accept: text/event-stream -> SSE framing", "text/event-stream" in ct and body.startswith("event: message\ndata: "), ct)

print("\n=== 10. manifest + CORS ===")
with U.urlopen(BASE + "/mcp/manifest", timeout=20) as rsp:
    man = json.loads(rsp.read().decode())
check("manifest lists same tool count", man["tool_count"] == len(tools), man.get("tool_count"))
req = U.Request(BASE + "/mcp", method="OPTIONS", headers={
    "Origin": "https://example.vercel.app",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type,mcp-protocol-version"})
with U.urlopen(req, timeout=20) as rsp:
    ch = {k.lower(): v for k, v in rsp.headers.items()}
check("CORS preflight allows origin", ch.get("access-control-allow-origin") == "*", ch)
st, hd, _ = post({"jsonrpc": "2.0", "id": 500, "method": "ping"}, headers={"Origin": "https://example.vercel.app"})
hl = {k.lower(): v for k, v in hd.items()}
check("CORS exposes Mcp-Session-Id (on real response)",
      "mcp-session-id" in hl.get("access-control-expose-headers", "").lower(),
      hl.get("access-control-expose-headers"))

print("\n=== 11. DELETE session ===")
req = U.Request(BASE + "/mcp", method="DELETE", headers={"Mcp-Session-Id": SESSION or "x"})
with U.urlopen(req, timeout=20) as rsp:
    check("DELETE /mcp -> 204", rsp.status == 204, rsp.status)

print(f"\n{'='*50}\n  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("  FAILURES: " + ", ".join(FAIL))
    sys.exit(1)
print("  ALL GREEN")

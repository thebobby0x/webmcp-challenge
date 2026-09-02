"""
Agent Registry UI — HTML dashboard served at /ui
Returns a styled HTML page showing all 5 agents with health, status, and live metrics.
Mount this router in api/main.py.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from registry.agent_registry import get_registry, AGENT_REGISTRY
from tools.event_tools import get_event_snapshot
import json

router = APIRouter()

@router.get("/ui", response_class=HTMLResponse)
async def agent_registry_ui():
    agents = get_registry()
    snapshot = get_event_snapshot()
    active_count = sum(1 for a in agents if a["status"] == "active")
    fleet_status_line = (
        "All systems operational"
        if active_count == len(agents)
        else f"{len(agents) - active_count} idle — configured by Fleet Architect"
    )
    agents_json = json.dumps(agents, indent=2)
    snapshot_json = json.dumps(snapshot, indent=2)

    return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>eventOS — Agent Fleet Registry</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  :root {{
    --noir: #0F0C0E;
    --surface: #1A1618;
    --raised: #242028;
    --riptide: #5DCBD1;
    --rosa: #F8BDD8;
    --amber: #FBBF24;
    --teal: #0D9488;
    --dim: #6B6670;
    --muted: #9D99A3;
    --bone: #F0ECF4;
  }}
  body {{ background: var(--noir); color: var(--bone); font-family: 'Archivo', sans-serif; min-height: 100vh; }}
  header {{ border-bottom: 1px solid #2A272C; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }}
  .logo {{ font-size: 18px; font-weight: 700; letter-spacing: -0.5px; }}
  .logo span {{ color: var(--riptide); }}
  .badge {{ background: rgba(93,203,209,0.12); color: var(--riptide); border: 1px solid rgba(93,203,209,0.3); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.05em; }}
  .imex-badge {{ background: rgba(251,191,36,0.1); color: var(--amber); border-color: rgba(251,191,36,0.3); }}
  .nav {{ display: flex; gap: 18px; align-items: center; }}
  .nav-link {{ color: var(--muted); text-decoration: none; font-size: 13px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.04em; }}
  .nav-link:hover {{ color: var(--riptide); }}
  .nav-link.active {{ color: var(--rosa); }}
  header {{ flex-wrap: wrap; gap: 12px; }}
  .status-dot.idle {{ background: var(--dim); }}
  .status-dot.error {{ background: #EF4444; box-shadow: 0 0 6px #EF4444; }}
  .status-dot.disabled {{ background: var(--raised); }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}
  h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 14px; margin-bottom: 32px; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 40px; }}
  .kpi {{ background: var(--surface); border: 1px solid #2A272C; border-radius: 10px; padding: 20px; }}
  .kpi-label {{ font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 8px; }}
  .kpi-value {{ font-size: 28px; font-weight: 700; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; }}
  .kpi-sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
  h2 {{ font-size: 16px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 16px; font-family: 'IBM Plex Mono', monospace; }}
  .agents-grid {{ display: grid; gap: 16px; margin-bottom: 40px; }}
  .agent-card {{ background: var(--surface); border: 1px solid #2A272C; border-radius: 12px; padding: 24px; display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: start; transition: border-color 0.2s; }}
  .agent-card:hover {{ border-color: rgba(93,203,209,0.3); }}
  .agent-card.compliance {{ border-left: 3px solid #EF4444; }}
  .agent-name {{ font-size: 17px; font-weight: 700; margin-bottom: 4px; }}
  .agent-role {{ font-size: 12px; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }}
  .agent-desc {{ font-size: 13px; color: var(--muted); line-height: 1.6; margin-bottom: 12px; }}
  .tags {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .tag {{ background: var(--raised); color: var(--dim); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; }}
  .agent-meta {{ text-align: right; min-width: 120px; }}
  .health {{ font-size: 32px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }}
  .health.good {{ color: var(--riptide); }}
  .health-label {{ font-size: 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; }}
  .status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .status-dot.active {{ background: var(--riptide); box-shadow: 0 0 6px var(--riptide); animation: pulse 2s infinite; }}
  @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
  .status-text {{ font-size: 12px; color: var(--muted); font-family: 'IBM Plex Mono', monospace; margin-top: 4px; }}
  .task-count {{ font-size: 11px; color: var(--dim); margin-top: 8px; font-family: 'IBM Plex Mono', monospace; }}
  .tools-list {{ margin-top: 12px; }}
  .tools-title {{ font-size: 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px; }}
  .snapshot {{ background: var(--surface); border: 1px solid #2A272C; border-radius: 12px; padding: 24px; }}
  .snap-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 16px; }}
  .snap-item {{ }}
  .snap-label {{ font-size: 11px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; margin-bottom: 4px; }}
  .snap-value {{ font-size: 20px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; color: var(--bone); }}
  footer {{ border-top: 1px solid #2A272C; padding: 20px 32px; margin-top: 40px; display: flex; justify-content: space-between; align-items: center; }}
  .footer-left {{ font-size: 12px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; }}
  .footer-right {{ font-size: 12px; color: var(--dim); }}
  .api-links {{ display: flex; gap: 12px; margin-top: 8px; }}
  .api-link {{ color: var(--riptide); text-decoration: none; font-size: 12px; font-family: 'IBM Plex Mono', monospace; }}
  .api-link:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<header>
  <div class="logo">event<span>OS</span> · Agent Fleet</div>
  <div class="nav">
    <a class="nav-link active" href="/ui">Agent Registry</a>
    <a class="nav-link" href="/ui/architect">Architect</a>
    <a class="nav-link" href="/ui/demo">Live Demo</a>
    <a class="nav-link" href="/docs">API Docs</a>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="badge">FORTIFIED ENTERPRISE FLEET</span>
    <span class="badge imex-badge">IMEX AMERICA · OCT 12–15</span>
  </div>
</header>

<main>
  <h1>Agent Registry</h1>
  <p class="subtitle">Central catalog of all agents — versioning, health, and real-time status</p>

  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-label">Agents Online</div>
      <div class="kpi-value">{active_count} / {len(agents)}</div>
      <div class="kpi-sub">{fleet_status_line}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Meeting Confirmation</div>
      <div class="kpi-value">{snapshot['confirmation_rate_pct']}%</div>
      <div class="kpi-sub">{snapshot['confirmed_meetings']} of {snapshot['total_meetings']}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Exhibitors</div>
      <div class="kpi-value">{snapshot['total_exhibitors']}</div>
      <div class="kpi-sub">{snapshot['unconfirmed_exhibitors']} unconfirmed</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Vendor Risk</div>
      <div class="kpi-value" style="color:{'var(--amber)' if snapshot['vendor_at_risk'] > 0 else 'var(--riptide)'}">{snapshot['vendor_at_risk']}</div>
      <div class="kpi-sub">vendors at risk</div>
    </div>
  </div>

  <h2>Fleet Agents</h2>
  <div class="agents-grid">
    {"".join(f'''
    <div class="agent-card {'compliance' if a['name'] == 'ComplianceAgent' else ''}">
      <div>
        <div class="agent-name">{a['name']}</div>
        <div class="agent-role">{a['role']}</div>
        <div class="agent-desc">{a['description']}</div>
        <div class="tags">{"".join(f'<span class="tag">{t}</span>' for t in a['tags'])}</div>
        <div class="tools-list">
          <div class="tools-title">Tools ({len(a['tools'])})</div>
          <div class="tags">{"".join(f'<span class="tag">{t}</span>' for t in a['tools'])}</div>
        </div>
      </div>
      <div class="agent-meta">
        <div class="health good">{a['health_score']:.0f}</div>
        <div class="health-label">health</div>
        <div class="status-text"><span class="status-dot {a['status']}"></span>{a['status']}</div>
        <div class="task-count">v{a['version']}</div>
        <div class="task-count">{a['task_count']} tasks run</div>
      </div>
    </div>''' for a in agents)}
  </div>

  <h2>Live Event Snapshot</h2>
  <div class="snapshot">
    <div class="snap-grid">
      <div class="snap-item"><div class="snap-label">Total Meetings</div><div class="snap-value">{snapshot['total_meetings']:,}</div></div>
      <div class="snap-item"><div class="snap-label">VIP Attendees</div><div class="snap-value">{snapshot['vip_attendees']}</div></div>
      <div class="snap-item"><div class="snap-label">Total Attendees</div><div class="snap-value">{snapshot['total_attendees']:,}</div></div>
    </div>
    <div style="margin-top:16px">
      <div class="api-links">
        <a class="api-link" href="/agents">→ /agents JSON</a>
        <a class="api-link" href="/demo/snapshot">→ /demo/snapshot</a>
        <a class="api-link" href="/docs">→ API docs</a>
        <a class="api-link" href="/ui/architect">→ Architect</a>
      </div>
    </div>
  </div>
</main>

<footer>
  <div class="footer-left">eventOS Agent Fleet v1.0.0 · Powered by Gemini 3.5 Flash + Google ADK</div>
  <div class="footer-right" style="font-size:11px;color:var(--dim);font-family:'IBM Plex Mono',monospace">Updated: {snapshot['timestamp']}</div>
</footer>

<script>
  // Auto-refresh KPIs every 30 seconds
  setTimeout(() => location.reload(), 30000);
</script>
</body>
</html>""")


# ─── Fleet Architect Page ─────────────────────────────────────────────────────
# Plain (non-f) string: the inline CSS/JS below uses literal braces.

ARCHITECT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>eventOS — Fleet Architect</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --noir: #0F0C0E;
    --surface: #1A1618;
    --raised: #242028;
    --riptide: #5DCBD1;
    --rosa: #F8BDD8;
    --amber: #FBBF24;
    --teal: #0D9488;
    --dim: #6B6670;
    --muted: #9D99A3;
    --bone: #F0ECF4;
    --line: #2A272C;
  }
  body { background: var(--noir); color: var(--bone); font-family: 'Archivo', sans-serif; min-height: 100vh; }
  header { border-bottom: 1px solid var(--line); padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
  .logo { font-size: 18px; font-weight: 700; letter-spacing: -0.5px; }
  .logo span { color: var(--riptide); }
  .nav { display: flex; gap: 18px; align-items: center; }
  .nav-link { color: var(--muted); text-decoration: none; font-size: 13px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.04em; }
  .nav-link:hover { color: var(--riptide); }
  .nav-link.active { color: var(--rosa); }
  .badge { background: rgba(93,203,209,0.12); color: var(--riptide); border: 1px solid rgba(93,203,209,0.3); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.05em; }
  .badge.rosa { background: rgba(248,189,216,0.1); color: var(--rosa); border-color: rgba(248,189,216,0.3); }
  main { max-width: 1200px; margin: 0 auto; padding: 32px; }
  h1 { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 14px; margin-bottom: 32px; max-width: 760px; line-height: 1.6; }
  .layout { display: grid; grid-template-columns: 380px 1fr; gap: 24px; align-items: start; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
  /* Grid children default to min-width:auto, which lets wide content stretch
     the panel past the viewport. Pin it so long strings wrap instead. */
  .layout > * { min-width: 0; }
  .panel { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 24px; overflow-wrap: anywhere; }
  h2 { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 18px; font-family: 'IBM Plex Mono', monospace; }
  label { display: block; font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px; }
  .field { margin-bottom: 16px; }
  input[type=text], input[type=number] {
    width: 100%; background: var(--noir); border: 1px solid var(--line); border-radius: 8px;
    color: var(--bone); font-family: 'Archivo', sans-serif; font-size: 14px; padding: 10px 12px; outline: none;
  }
  input:focus { border-color: var(--riptide); }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .feature-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
  .feature { display: flex; align-items: center; gap: 10px; background: var(--noir); border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; cursor: pointer; }
  .feature:hover { border-color: rgba(93,203,209,0.35); }
  .feature input { width: 15px; height: 15px; accent-color: #5DCBD1; cursor: pointer; }
  .feature span { font-size: 13px; color: var(--bone); text-transform: none; letter-spacing: 0; }
  .feature input:not(:checked) + span { color: var(--dim); }
  .add-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
  button.add { background: var(--raised); color: var(--muted); border: 1px solid var(--line); border-radius: 8px; padding: 0 14px; font-family: 'IBM Plex Mono', monospace; font-size: 13px; cursor: pointer; }
  button.add:hover { color: var(--riptide); border-color: rgba(93,203,209,0.35); }
  button.primary {
    width: 100%; background: var(--riptide); color: #06282A; border: none; border-radius: 8px;
    padding: 13px 16px; font-family: 'Archivo', sans-serif; font-size: 14px; font-weight: 700; cursor: pointer;
    letter-spacing: 0.02em; margin-top: 20px;
  }
  button.primary:hover { background: #7BD8DD; }
  button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .hint { font-size: 11px; color: var(--dim); margin-top: 10px; font-family: 'IBM Plex Mono', monospace; text-align: center; }
  .placeholder { color: var(--dim); font-size: 13px; line-height: 1.7; }
  .loading { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; text-align: center; }
  .spinner { width: 40px; height: 40px; border: 2px solid var(--line); border-top-color: var(--riptide); border-radius: 50%; animation: spin 0.9s linear infinite; margin-bottom: 20px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-text { font-size: 14px; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; }
  .loading-sub { font-size: 12px; color: var(--dim); margin-top: 8px; }
  .fleet-name { font-size: 20px; font-weight: 700; margin-bottom: 10px; }
  .meta-row { display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 22px; }
  .meta { font-size: 11px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; }
  .meta b { color: var(--bone); font-weight: 500; }
  .rationale { background: var(--noir); border: 1px solid var(--line); border-left: 3px solid var(--rosa); border-radius: 8px; padding: 16px; font-size: 13px; color: var(--muted); line-height: 1.7; margin-bottom: 26px; }
  .section { margin-bottom: 26px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
  .card { background: var(--noir); border: 1px solid var(--line); border-left: 3px solid var(--dim); border-radius: 10px; padding: 18px; }
  .card.critical { border-left-color: var(--rosa); }
  .card.high { border-left-color: var(--riptide); }
  .card.standard { border-left-color: var(--teal); }
  .card-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 4px; }
  .card-name { font-size: 16px; font-weight: 700; }
  .card-role { font-size: 11px; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px; line-height: 1.5; }
  .cap-title { font-size: 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 8px; }
  ul.caps { list-style: none; margin-bottom: 14px; }
  ul.caps li { font-size: 13px; color: var(--muted); line-height: 1.55; padding-left: 14px; position: relative; margin-bottom: 6px; }
  ul.caps li:before { content: '▸'; position: absolute; left: 0; color: var(--riptide); }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { background: var(--raised); color: var(--dim); border-radius: 4px; padding: 2px 8px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; }
  .chip { font-size: 10px; font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; padding: 3px 9px; border-radius: 20px; white-space: nowrap; }
  .chip.critical { background: rgba(248,189,216,0.12); color: var(--rosa); border: 1px solid rgba(248,189,216,0.3); }
  .chip.high { background: rgba(93,203,209,0.12); color: var(--riptide); border: 1px solid rgba(93,203,209,0.3); }
  .chip.standard { background: var(--raised); color: var(--muted); border: 1px solid var(--line); }
  .deploy-bar { border-top: 1px solid var(--line); padding-top: 22px; margin-top: 4px; }
  button.deploy { background: var(--rosa); color: #2A0F1E; border: none; border-radius: 8px; padding: 13px 24px; font-family: 'Archivo', sans-serif; font-weight: 700; font-size: 14px; cursor: pointer; }
  button.deploy:hover { background: #FBD2E4; }
  button.deploy:disabled { opacity: 0.5; cursor: not-allowed; }
  .deploy-hint { font-size: 11px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; margin-top: 10px; }
  .ok { background: rgba(93,203,209,0.07); border: 1px solid rgba(93,203,209,0.3); color: var(--riptide); border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.7; margin-top: 16px; }
  .ok a { color: var(--rosa); }
  .error { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.35); color: #FCA5A5; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.6; }
  details summary { cursor: pointer; font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 12px; }
  pre { background: var(--noir); border: 1px solid var(--line); border-radius: 8px; padding: 16px; overflow: auto; font-family: 'IBM Plex Mono', monospace; font-size: 12px; line-height: 1.6; color: var(--riptide); max-height: 420px; white-space: pre-wrap; word-break: break-word; }
  footer { border-top: 1px solid var(--line); padding: 20px 32px; margin-top: 40px; font-size: 12px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; }
</style>
</head>
<body>
<header>
  <div class="logo">event<span>OS</span> · Fleet Architect</div>
  <div class="nav">
    <a class="nav-link" href="/ui">Agent Registry</a>
    <a class="nav-link active" href="/ui/architect">Architect</a>
    <a class="nav-link" href="/ui/demo">Live Demo</a>
    <a class="nav-link" href="/docs">API Docs</a>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="badge rosa">singularityLab</span>
    <span class="badge">LIVE LLM</span>
  </div>
</header>

<main>
  <h1>Fleet Architect</h1>
  <p class="subtitle">
    Describe the event. The architect calls the model live and designs a complete Google ADK
    agent fleet for it — every agent's role, capabilities, and bound tools. Deploy the result
    straight into the live Agent Registry.
  </p>

  <div class="layout">
    <div class="panel">
      <h2>Event Profile</h2>
      <form id="architect-form">
        <div class="field">
          <label for="event_name">Event Name</label>
          <input type="text" id="event_name" value="IMEX America 2026" required>
        </div>
        <div class="row">
          <div class="field">
            <label for="attendees">Attendees</label>
            <input type="number" id="attendees" value="12000" min="1" required>
          </div>
          <div class="field">
            <label for="exhibitors">Exhibitors</label>
            <input type="number" id="exhibitors" value="3500" min="0">
          </div>
        </div>
        <div class="field">
          <label for="days">Duration (days)</label>
          <input type="number" id="days" value="3" min="1" required>
        </div>

        <label>Required Features</label>
        <div class="feature-list" id="feature-list"></div>
        <div class="add-row">
          <input type="text" id="feature-input" placeholder="Add a feature…">
          <button type="button" class="add" id="add-feature">Add</button>
        </div>

        <button type="submit" class="primary" id="submit-btn">Design Fleet &rarr;</button>
        <div class="hint">POST /architect &middot; live model call</div>
      </form>
    </div>

    <div class="panel">
      <h2>Fleet Specification</h2>
      <div id="result">
        <p class="placeholder">
          No fleet designed yet. The form is pre-filled with the IMEX America 2026 profile —
          hit <b>Design Fleet</b> to generate a real spec.
        </p>
      </div>
    </div>
  </div>
</main>

<footer>eventOS Agent Fleet v1.0.0 &middot; singularityLab architect layer &middot; live model-generated fleet specs</footer>

<script>
const DEFAULT_FEATURES = ['VIP concierge', 'GDPR compliance', 'multi-language', 'real-time analytics'];

const form = document.getElementById('architect-form');
const resultEl = document.getElementById('result');
const submitBtn = document.getElementById('submit-btn');
const featureList = document.getElementById('feature-list');
const featureInput = document.getElementById('feature-input');

let lastSpec = null;

function esc(s) {
  return String(s === undefined || s === null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function addFeature(name, checked) {
  const label = document.createElement('label');
  label.className = 'feature';
  label.innerHTML = '<input type="checkbox" ' + (checked ? 'checked' : '') + '>'
                  + '<span>' + esc(name) + '</span>';
  label.querySelector('input').value = name;
  featureList.appendChild(label);
}

DEFAULT_FEATURES.forEach(function (f) { addFeature(f, true); });

document.getElementById('add-feature').addEventListener('click', function () {
  const value = featureInput.value.trim();
  if (!value) return;
  addFeature(value, true);
  featureInput.value = '';
});

featureInput.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') { e.preventDefault(); document.getElementById('add-feature').click(); }
});

function selectedFeatures() {
  return Array.prototype.slice
    .call(featureList.querySelectorAll('input:checked'))
    .map(function (i) { return i.value; });
}

function priorityClass(p) {
  const v = String(p || '').toLowerCase();
  return (v === 'critical' || v === 'high' || v === 'standard') ? v : 'standard';
}

function renderFleet(data) {
  const agents = Array.isArray(data.agents) ? data.agents : [];

  let html = '<div class="fleet-name">' + esc(data.fleet_name) + '</div>';

  html += '<div class="meta-row">'
       + '<div class="meta">model <b>' + esc(data.model) + '</b></div>'
       + '<div class="meta">llm latency <b>' + esc(data.llm_latency_ms) + 'ms</b></div>'
       + '<div class="meta">agents <b>' + agents.length + '</b></div>'
       + '<div class="meta">generated <b>' + esc(data.generated_at) + '</b></div>'
       + '</div>';

  if (data.rationale) {
    html += '<div class="rationale">' + esc(data.rationale) + '</div>';
  }

  html += '<div class="section"><h2>Agent Fleet (' + agents.length + ')</h2><div class="cards">';
  agents.forEach(function (a) {
    const cls = priorityClass(a.priority);
    const caps = Array.isArray(a.capabilities) ? a.capabilities : [];
    const tools = Array.isArray(a.tools) ? a.tools : [];
    html += '<div class="card ' + cls + '">'
         + '<div class="card-head"><div class="card-name">' + esc(a.name) + '</div>'
         + '<span class="chip ' + cls + '">' + esc(a.priority || 'standard') + '</span></div>'
         + '<div class="card-role">' + esc(a.role) + '</div>';
    if (caps.length) {
      html += '<div class="cap-title">Capabilities</div><ul class="caps">'
           + caps.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join('')
           + '</ul>';
    }
    if (tools.length) {
      html += '<div class="cap-title">Tools (' + tools.length + ')</div><div class="tags">'
           + tools.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('')
           + '</div>';
    }
    html += '</div>';
  });
  html += '</div></div>';

  html += '<div class="section"><details><summary>Raw fleet spec JSON</summary>'
       + '<pre>' + esc(JSON.stringify(lastSpec, null, 2)) + '</pre></details></div>';

  html += '<div class="deploy-bar">'
       + '<button type="button" class="deploy" id="deploy-btn">Deploy Fleet &rarr;</button>'
       + '<div class="deploy-hint">POST /run &middot; registers these agents in the live Agent Registry</div>'
       + '<div id="deploy-result"></div></div>';

  resultEl.innerHTML = html;
  document.getElementById('deploy-btn').addEventListener('click', deployFleet);
}

async function deployFleet() {
  const btn = document.getElementById('deploy-btn');
  const out = document.getElementById('deploy-result');
  btn.disabled = true;
  out.innerHTML = '<div class="deploy-hint">Deploying…</div>';

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(lastSpec)
    });
    const data = await res.json();
    if (!res.ok) {
      out.innerHTML = '<div class="error"><b>Deploy failed (' + res.status + ')</b><br>'
        + esc(data.detail || JSON.stringify(data)) + '</div>';
    } else {
      const deployed = data.deployed_agents || [];
      const idle = data.idle_agents || [];
      out.innerHTML = '<div class="ok"><b>' + esc(data.fleet_name) + ' deployed</b><br>'
        + deployed.length + ' agent(s) active: ' + esc(deployed.join(', ')) + '<br>'
        + idle.length + ' idled: ' + esc(idle.join(', ')) + '<br>'
        + '<a href="/ui">→ View in Agent Registry</a></div>';
    }
  } catch (err) {
    out.innerHTML = '<div class="error"><b>Deploy request failed</b><br>' + esc(err.message) + '</div>';
  } finally {
    btn.disabled = false;
  }
}

form.addEventListener('submit', async function (e) {
  e.preventDefault();
  submitBtn.disabled = true;
  lastSpec = null;
  resultEl.innerHTML = '<div class="loading"><div class="spinner"></div>'
    + '<div class="loading-text">Designing your agent fleet…</div>'
    + '<div class="loading-sub">Live model call · this takes a few seconds</div></div>';

  const payload = {
    event_name: document.getElementById('event_name').value,
    attendees: parseInt(document.getElementById('attendees').value, 10),
    exhibitors: parseInt(document.getElementById('exhibitors').value, 10) || 0,
    days: parseInt(document.getElementById('days').value, 10),
    features: selectedFeatures()
  };

  try {
    const res = await fetch('/architect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      resultEl.innerHTML = '<div class="error"><b>Architect failed (' + res.status + ')</b><br>'
        + esc(data.detail || JSON.stringify(data)) + '</div>';
    } else {
      // The deploy contract is exactly the three documented fields.
      lastSpec = { fleet_name: data.fleet_name, agents: data.agents, rationale: data.rationale };
      renderFleet(data);
    }
  } catch (err) {
    resultEl.innerHTML = '<div class="error"><b>Request failed</b><br>' + esc(err.message) + '</div>';
  } finally {
    submitBtn.disabled = false;
  }
});
</script>
</body>
</html>"""


@router.get("/ui/architect", response_class=HTMLResponse)
async def fleet_architect_ui():
    """singularityLab Fleet Architect — form + live fleet spec rendering."""
    return HTMLResponse(content=ARCHITECT_HTML)


DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>eventOS — Live Demo</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --noir: #0F0C0E; --surface: #1A1618; --raised: #242028;
    --riptide: #5DCBD1; --rosa: #F8BDD8; --amber: #FBBF24;
    --green: #34D399; --red: #EF4444; --dim: #6B6670;
    --muted: #9D99A3; --bone: #F0ECF4;
  }
  body { background: var(--noir); color: var(--bone); font-family: 'Archivo', sans-serif; min-height: 100vh; }
  header { border-bottom: 1px solid #2A272C; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
  .logo { font-size: 18px; font-weight: 700; letter-spacing: -0.5px; }
  .logo span { color: var(--riptide); }
  .nav { display: flex; gap: 18px; align-items: center; }
  .nav-link { color: var(--muted); text-decoration: none; font-size: 13px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.04em; }
  .nav-link:hover { color: var(--riptide); }
  .nav-link.active { color: var(--rosa); }
  .badge { background: rgba(93,203,209,0.12); color: var(--riptide); border: 1px solid rgba(93,203,209,0.3); border-radius: 20px; padding: 4px 12px; font-size: 11px; font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.05em; }
  .badge-amber { background: rgba(251,191,36,0.1); color: var(--amber); border-color: rgba(251,191,36,0.3); }
  main { max-width: 1100px; margin: 0 auto; padding: 32px; }
  h1 { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 14px; margin-bottom: 32px; }
  .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 40px; }
  .kpi { background: var(--surface); border: 1px solid #2A272C; border-radius: 10px; padding: 20px; }
  .kpi-label { font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 8px; }
  .kpi-value { font-size: 28px; font-weight: 700; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; }
  .kpi-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .demo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
  .panel { background: var(--surface); border: 1px solid #2A272C; border-radius: 14px; padding: 28px; display: flex; flex-direction: column; gap: 16px; }
  .panel-header { display: flex; align-items: center; gap: 12px; }
  .panel-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
  .icon-conflict { background: rgba(251,191,36,0.12); }
  .icon-insight { background: rgba(93,203,209,0.12); }
  .panel-title { font-size: 17px; font-weight: 700; }
  .panel-agent { font-size: 11px; color: var(--riptide); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }
  .panel-desc { font-size: 13px; color: var(--muted); line-height: 1.6; }
  .query-input { background: var(--raised); border: 1px solid #3A373C; border-radius: 8px; color: var(--bone); font-size: 13px; font-family: 'Archivo', sans-serif; padding: 10px 14px; width: 100%; resize: none; height: 72px; outline: none; }
  .query-input:focus { border-color: rgba(93,203,209,0.4); }
  .trigger-btn { background: var(--riptide); color: var(--noir); font-size: 14px; font-weight: 700; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-family: 'Archivo', sans-serif; letter-spacing: 0.01em; display: flex; align-items: center; gap: 8px; justify-content: center; transition: opacity 0.15s; }
  .trigger-btn:hover { opacity: 0.88; }
  .trigger-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .trigger-btn.conflict { background: var(--amber); }
  .result-box { background: var(--raised); border: 1px solid #3A373C; border-radius: 10px; padding: 20px; min-height: 120px; font-size: 13px; line-height: 1.6; display: none; }
  .result-box.show { display: block; }
  .result-headline { font-size: 14px; font-weight: 600; color: var(--bone); margin-bottom: 12px; }
  .result-section { margin-bottom: 14px; }
  .result-section-label { font-size: 10px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.1em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 6px; }
  .rec-item { display: flex; gap: 8px; margin-bottom: 6px; color: var(--muted); }
  .rec-item::before { content: "→"; color: var(--riptide); flex-shrink: 0; }
  .risk-item { display: flex; gap: 8px; margin-bottom: 6px; color: var(--amber); }
  .risk-item::before { content: "⚠"; flex-shrink: 0; }
  .conflict-item { background: rgba(251,191,36,0.07); border: 1px solid rgba(251,191,36,0.2); border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; }
  .conflict-time { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--amber); margin-bottom: 3px; }
  .conflict-name { font-size: 13px; font-weight: 600; }
  .conflict-detail { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .kpi-mini { display: flex; gap: 12px; flex-wrap: wrap; }
  .kpi-mini-item { background: var(--surface); border: 1px solid #2A272C; border-radius: 6px; padding: 8px 12px; }
  .kpi-mini-label { font-size: 10px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; text-transform: uppercase; }
  .kpi-mini-val { font-size: 18px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; color: var(--riptide); }
  .spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.2); border-top-color: var(--riptide); border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .loading-row { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 13px; }
  .powered { font-size: 11px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; margin-top: 10px; }
  .snapshot-strip { background: var(--surface); border: 1px solid #2A272C; border-radius: 12px; padding: 20px 24px; margin-bottom: 32px; }
  .snapshot-strip h2 { font-size: 11px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.1em; font-family: 'IBM Plex Mono', monospace; margin-bottom: 14px; }
  footer { border-top: 1px solid #2A272C; padding: 20px 32px; margin-top: 40px; display: flex; justify-content: space-between; }
  .footer-text { font-size: 12px; color: var(--dim); font-family: 'IBM Plex Mono', monospace; }
  .status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--riptide); box-shadow: 0 0 5px var(--riptide); animation: pulse 2s infinite; margin-right: 6px; }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
  @media (max-width: 720px) { .demo-grid { grid-template-columns: 1fr; } .kpi-row { grid-template-columns: repeat(2,1fr); } }
</style>
</head>
<body>
<header>
  <div class="logo">event<span>OS</span> · Agent Fleet</div>
  <div class="nav">
    <a class="nav-link" href="/ui">Agent Registry</a>
    <a class="nav-link" href="/ui/architect">Architect</a>
    <a class="nav-link active" href="/ui/demo">Live Demo</a>
    <a class="nav-link" href="/docs">API Docs</a>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="badge">FORTIFIED ENTERPRISE FLEET</span>
    <span class="badge badge-amber">IMEX AMERICA · OCT 12–15</span>
  </div>
</header>

<main>
  <h1>Live Agent Demo</h1>
  <p class="subtitle">Trigger real agent workflows — conflict detection, executive insight, live KPI snapshot</p>

  <div class="kpi-row" id="kpi-row">
    <div class="kpi"><div class="kpi-label">Meetings</div><div class="kpi-value" id="k-meetings">—</div><div class="kpi-sub" id="k-meetings-sub">loading…</div></div>
    <div class="kpi"><div class="kpi-label">Confirmation Rate</div><div class="kpi-value" id="k-confirm">—</div><div class="kpi-sub">of scheduled meetings</div></div>
    <div class="kpi"><div class="kpi-label">Exhibitors</div><div class="kpi-value" id="k-exhibitors">—</div><div class="kpi-sub" id="k-ex-sub">loading…</div></div>
    <div class="kpi"><div class="kpi-label">Vendor Risk</div><div class="kpi-value" id="k-risk" style="color:var(--amber)">—</div><div class="kpi-sub">vendors flagged</div></div>
  </div>

  <div class="demo-grid">

    <!-- CONFLICT RESOLUTION -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-icon icon-conflict">⚡</div>
        <div>
          <div class="panel-title">Conflict Resolution</div>
          <div class="panel-agent">BookingAgent + CommsAgent</div>
        </div>
      </div>
      <p class="panel-desc">Detects scheduling conflicts for an attendee and triggers automatic communications. Simulates a cascade resolution across the agent fleet.</p>
      <button class="trigger-btn conflict" id="btn-conflict" onclick="runConflict()">
        ⚡ Trigger Conflict Resolution
      </button>
      <div class="result-box" id="result-conflict"></div>
    </div>

    <!-- INSIGHT BRIEFING -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-icon icon-insight">📊</div>
        <div>
          <div class="panel-title">Executive Briefing</div>
          <div class="panel-agent">InsightAgent · Gemini 3.5 Flash</div>
        </div>
      </div>
      <p class="panel-desc">InsightAgent synthesizes live event KPIs into an executive briefing with actionable recommendations and risk horizon analysis.</p>
      <textarea class="query-input" id="insight-query">Give me an executive briefing on the current event health.</textarea>
      <button class="trigger-btn" id="btn-insight" onclick="runInsight()">
        📊 Generate Executive Briefing
      </button>
      <div class="result-box" id="result-insight"></div>
    </div>

  </div>

</main>

<footer>
  <span class="footer-text"><span class="status-dot"></span>eventOS Agent Fleet · us-central1</span>
  <span class="footer-text">studio0x · All Things Agentic Hackathon 2026</span>
</footer>

<script>
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

async function loadSnapshot() {
  try {
    const res = await fetch('/demo/snapshot');
    const data = await res.json();
    const s = data.snapshot || data;
    document.getElementById('k-meetings').textContent = s.total_meetings ?? '—';
    document.getElementById('k-meetings-sub').textContent = s.confirmed_meetings + ' confirmed';
    document.getElementById('k-confirm').textContent = (s.confirmation_rate_pct ?? '—') + '%';
    document.getElementById('k-exhibitors').textContent = s.total_exhibitors ?? '—';
    document.getElementById('k-ex-sub').textContent = s.unconfirmed_exhibitors + ' unconfirmed';
    const risk = s.vendor_at_risk ?? 0;
    document.getElementById('k-risk').textContent = risk;
    document.getElementById('k-risk').style.color = risk > 0 ? 'var(--amber)' : 'var(--riptide)';
  } catch(e) { console.warn('snapshot load failed', e); }
}

async function runConflict() {
  const btn = document.getElementById('btn-conflict');
  const box = document.getElementById('result-conflict');
  btn.disabled = true;
  box.className = 'result-box show';
  box.innerHTML = '<div class="loading-row"><div class="spinner"></div>BookingAgent scanning schedule conflicts…</div>';
  try {
    const res = await fetch('/demo/conflict', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
    const d = await res.json();
    const conflicts = d.conflicts || [];
    let html = '<div class="result-section-label">Conflicts Detected — ' + d.conflicts_detected + '</div>';
    if (conflicts.length === 0) {
      html += '<div style="color:var(--green)">✓ No scheduling conflicts found for ' + esc(d.attendee_id) + '</div>';
    } else {
      conflicts.forEach(c => {
        html += '<div class="conflict-item">';
        html += '<div class="conflict-time">' + esc(c.time || c.date || '') + '</div>';
        html += '<div class="conflict-name">' + esc(c.meeting_name || c.name || JSON.stringify(c)) + '</div>';
        if (c.location) html += '<div class="conflict-detail">📍 ' + esc(c.location) + '</div>';
        if (c.exhibitor_name) html += '<div class="conflict-detail">Company: ' + esc(c.exhibitor_name) + '</div>';
        html += '</div>';
      });
    }
    if (d.action_taken) {
      html += '<div class="result-section" style="margin-top:12px"><div class="result-section-label">Agent Action</div>';
      html += '<div class="rec-item">' + esc(d.action_taken) + '</div></div>';
    }
    html += '<div class="powered">Resolved by BookingAgent + CommsAgent · eventOS Agent Fleet</div>';
    box.innerHTML = html;
  } catch(e) {
    box.innerHTML = '<div style="color:var(--red)">Request failed: ' + esc(e.message) + '</div>';
  }
  btn.disabled = false;
}

async function runInsight() {
  const btn = document.getElementById('btn-insight');
  const box = document.getElementById('result-insight');
  const query = document.getElementById('insight-query').value.trim() || 'Give me an executive briefing on the current event health.';
  btn.disabled = true;
  box.className = 'result-box show';
  box.innerHTML = '<div class="loading-row"><div class="spinner"></div>InsightAgent synthesizing event data…</div>';
  try {
    const res = await fetch('/demo/insight', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ query })
    });
    const d = await res.json();
    let html = '';
    if (d.headline) {
      html += '<div class="result-headline">' + esc(d.headline) + '</div>';
    }
    if (d.kpis) {
      const k = d.kpis;
      html += '<div class="result-section"><div class="result-section-label">Live KPIs</div><div class="kpi-mini">';
      html += '<div class="kpi-mini-item"><div class="kpi-mini-label">Meetings</div><div class="kpi-mini-val">' + (k.total_meetings||'—') + '</div></div>';
      html += '<div class="kpi-mini-item"><div class="kpi-mini-label">Confirm Rate</div><div class="kpi-mini-val">' + (k.confirmation_rate_pct||'—') + '%</div></div>';
      html += '<div class="kpi-mini-item"><div class="kpi-mini-label">Exhibitors</div><div class="kpi-mini-val">' + (k.total_exhibitors||'—') + '</div></div>';
      html += '<div class="kpi-mini-item"><div class="kpi-mini-label">Vendor Risk</div><div class="kpi-mini-val" style="color:var(--amber)">' + (k.vendor_at_risk||0) + '</div></div>';
      html += '</div></div>';
    }
    if (d.recommendations && d.recommendations.length) {
      html += '<div class="result-section"><div class="result-section-label">Recommendations</div>';
      d.recommendations.forEach(r => { html += '<div class="rec-item">' + esc(r) + '</div>'; });
      html += '</div>';
    }
    if (d.risk_horizon_2hrs && d.risk_horizon_2hrs.length) {
      html += '<div class="result-section"><div class="result-section-label">Risk Horizon — Next 2 Hours</div>';
      d.risk_horizon_2hrs.forEach(r => { html += '<div class="risk-item">' + esc(r) + '</div>'; });
      html += '</div>';
    }
    html += '<div class="powered">Generated by ' + esc(d.powered_by || 'InsightAgent') + ' · ' + esc(d.briefing_generated_at || '') + '</div>';
    box.innerHTML = html;
  } catch(e) {
    box.innerHTML = '<div style="color:var(--red)">Request failed: ' + esc(e.message) + '</div>';
  }
  btn.disabled = false;
}

loadSnapshot();
</script>
</body>
</html>"""


@router.get("/ui/demo", response_class=HTMLResponse)
async def demo_ui():
    """Live demo page — one-click triggers for conflict resolution and insight briefing."""
    return HTMLResponse(content=DEMO_HTML)

# eventOS: The Enterprise Event Fleet
### All Things Agentic Hackathon — Fortified Enterprise Fleet Track

> **5 AI agents that run the event while you run the strategy.**

The global events industry is a $1.5 trillion sector run on spreadsheets, email chains, and heroic humans. A single IMEX conference involves 10,000+ attendees, 3,500+ exhibitors, and 15,000+ scheduled meetings — all coordinated manually. When a venue changes, a VIP cancels, or a scheduling conflict cascades, there's no intelligent system to adapt. Event teams burn out. Attendees get bad experiences. Revenue is lost.

**eventOS deploys a Fortified Enterprise Fleet of purpose-built AI agents that runs the event while humans run the strategy.**

---

## The Agent Fleet

| Agent | Role | Key Capability |
|-------|------|----------------|
| **BookingAgent** | Meeting Orchestration | Detects conflicts, reroutes asynchronously, sends confirmations — 15,000 meetings, no human required |
| **CommsAgent** | Attendee Communications | Routes email/SMS/push based on preference; escalates only when human authority required |
| **InsightAgent** | Real-Time Intelligence | Generates proactive executive briefings; flags anomalies before they become incidents |
| **ComplianceAgent** | GDPR/CCPA Enforcement | Inline guardrail on every agent output; zero PII leaks by design |
| **VendorAgent** | Vendor SLA Management | Tracks F&B/AV/logistics deliverables; fires alerts 48→24→6 hours before breach |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Agent Framework** | Google ADK (`google-adk`) |
| **Intelligence** | Gemini 2.0 Flash via Gemini API |
| **Edge AI** | Gemma 4 (on-device, offline stadium kiosk) |
| **Compute** | Google Cloud Run (serverless, auto-scale to 0) |
| **Agent Memory** | Firestore (cross-session persistent context) |
| **Messaging** | Pub/Sub (async inter-agent communication) |
| **Monitoring** | Vertex AI + Cloud Logging (OpenTelemetry traces) |
| **API** | FastAPI |

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/thebobby0x/hackathon-agentic
cd hackathon-agentic
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Add your GEMINI_API_KEY from https://aistudio.google.com/apikey

# 3. Run locally
uvicorn api.main:app --reload --port 8080

# 4. Open the Agent Registry
open http://localhost:8080/agents

# 5. Try the demos
curl -X POST http://localhost:8080/demo/conflict -H "Content-Type: application/json" -d '{"attendee_id": "ATT-0001"}'
curl -X POST http://localhost:8080/demo/insight -H "Content-Type: application/json" -d '{"query": "Give me the executive briefing."}'
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/agents` | **Agent Registry** — all agents, status, health scores |
| `GET` | `/agents/{name}` | Single agent status |
| `POST` | `/agents/{name}/run` | Invoke an agent with a task |
| `POST` | `/demo/conflict` | Demo: conflict cascade resolution |
| `POST` | `/demo/insight` | Demo: executive briefing generation |
| `GET` | `/demo/snapshot` | Live event KPI snapshot |
| `GET` | `/health` | Health check |

---

## Deploy to Cloud Run

```bash
# Set your project
export GOOGLE_CLOUD_PROJECT=your-project-id

# Add your Gemini API key as a secret
echo -n "your_gemini_api_key" | gcloud secrets create gemini-api-key --data-file=-

# Deploy
chmod +x deploy.sh
./deploy.sh
```

The deploy script outputs your `*.run.app` URL — this is your live demo URL for the submission.

---

## Architecture

```
[Event Organizer]
       │
       ▼
[Agent Gateway / FastAPI]
       │
  ┌────┴────┐
  │         │
  ▼         ▼
[Pub/Sub]  [Agent Registry]
  │
  ├──▶ [BookingAgent] ──▶ Gemini 2.0 Flash ──▶ Firestore
  ├──▶ [CommsAgent]   ──▶ Gemini 2.0 Flash ──▶ Email/SMS/Push
  ├──▶ [InsightAgent] ──▶ Gemini 2.0 Flash ──▶ Executive Brief
  ├──▶ [ComplianceAgent] (inline on all outputs)
  └──▶ [VendorAgent]  ──▶ Gemini 2.0 Flash ──▶ SLA Alerts

[Edge Layer — Offline Venues]
  └──▶ [Gemma 4 on-device] ──▶ Check-in kiosk, wayfinding, Q&A
       (zero cloud dependency, $0/token, syncs when connected)
```

---

## Why This Wins

- **Not a prototype.** eventOS demos live at IMEX America, October 12–15, 2026 — 6 weeks post-submission.
- **Offline-first edge AI.** Convention centers have poor WiFi. Gemma 4 runs on-device for check-in, wayfinding, and attendee Q&A at $0/token. No other team has this.
- **Compliance by design.** ComplianceAgent is an inline guardrail, not a bolt-on audit. GDPR enforcement runs on every agent output.
- **Fortified Enterprise Fleet architecture.** Agent Registry, Runtime, Memory Bank, Identity, Gateway, Observability — all five track requirements, all present.

---

## About studio0x

studio0x is an AI software studio building vertical AI operating systems. eventOS is the AI OS for the $1.5T events industry. Incorporated. Real customers. Shipping in October.

**Contact:** b@studio0x.io | studio0x.io

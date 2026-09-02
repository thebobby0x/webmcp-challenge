# Cloud Run Deploy Guide — 10 Minutes to Live URL

Run these commands in order. Each block is copy-paste ready.

---

## Step 1 — Authenticate gcloud (2 min)

```bash
# Check if gcloud is installed
gcloud version

# If not installed:
brew install --cask google-cloud-sdk

# Log in (opens browser)
gcloud auth login
gcloud auth application-default login
```

---

## Step 2 — Create project + enable APIs (3 min)

```bash
# Create a new project (or use existing)
export PROJECT_ID="eventos-hackathon-$(date +%s)"
gcloud projects create $PROJECT_ID --name="eventOS Hackathon"

# Set it as default
gcloud config set project $PROJECT_ID

# Enable billing (required for Cloud Run)
# Go to: https://console.cloud.google.com/billing
# Link your billing account to $PROJECT_ID — then come back

# Enable all required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com

echo "✅ APIs enabled"
```

---

## Step 3 — Add your Gemini API key as a secret (1 min)

```bash
# Get your key from https://aistudio.google.com/apikey
# Then run (replace YOUR_KEY):
echo -n "YOUR_GEMINI_API_KEY" | \
  gcloud secrets create gemini-api-key \
  --data-file=- \
  --replication-policy=automatic

echo "✅ Secret stored"
```

---

## Step 4 — Deploy to Cloud Run (3 min)

```bash
cd ~/Desktop/hackathon-agentic

# Export project ID (if new terminal)
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
export GOOGLE_CLOUD_REGION=us-central1

# Make deploy script executable and run
chmod +x deploy.sh
./deploy.sh
```

The script outputs your live URL — it looks like:
```
https://eventos-agent-fleet-xxxxxxxxxx-uc.a.run.app
```

**Copy that URL — it goes in the Devpost submission.**

---

## Step 5 — Verify it's live (30 sec)

```bash
# Replace with your actual URL
export FLEET_URL="https://eventos-agent-fleet-xxxxxxxxxx-uc.a.run.app"

# Check the agent registry
curl "$FLEET_URL/agents" | python3 -m json.tool

# Run the conflict demo
curl -X POST "$FLEET_URL/demo/conflict" \
  -H "Content-Type: application/json" \
  -d '{"attendee_id": "ATT-0001"}' | python3 -m json.tool

# Run the insight demo
curl -X POST "$FLEET_URL/demo/insight" \
  -H "Content-Type: application/json" \
  -d '{"query": "Give me the executive briefing."}' | python3 -m json.tool
```

If all three return JSON — you're live. Start recording.

---

## Step 6 — Record the demo (4 min)

Use QuickTime Player → New Screen Recording. Record your browser hitting:

1. Open `hackathon-agentic-architecture.html` in browser — show it for 10 sec
2. Browser to `$FLEET_URL/agents` — show the 5-agent registry
3. Run the conflict demo in browser or terminal — show the response
4. Run the insight demo — show the executive briefing
5. Show the Cloud Run dashboard at console.cloud.google.com/run
6. Close with: "Demoing live at IMEX America, October 12-15."

---

## Step 7 — Submit on Devpost (2 min)

1. Go to https://allthingsagentichackathon.devpost.com
2. Click "Enter Hackathon" → use b@studio0x.io
3. Select track: **Fortified Enterprise Fleet**
4. Paste from `hackathon-devpost-copy.md`
5. Add your Cloud Run URL as the Project URL
6. Add GitHub repo URL (push hackathon-agentic to GitHub first)
7. Upload the demo video
8. Submit

---

## Push to GitHub (do before submitting)

```bash
cd ~/Desktop/hackathon-agentic

# Init and push (or add to existing account)
gh repo create hackathon-agentic --public --source=. --remote=origin --push

# The public repo URL is what Devpost needs
```

---

## Total time estimate

| Step | Time |
|------|------|
| gcloud auth | 2 min |
| Create project + enable APIs | 3 min |
| Add secret | 1 min |
| Deploy | 3 min |
| Verify + demo endpoints | 1 min |
| Record video | 4 min |
| Submit on Devpost | 2 min |
| **Total** | **~16 min** |

You have 51 hours. No rush — but earlier = more time to fix anything unexpected.

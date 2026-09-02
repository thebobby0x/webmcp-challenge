#!/bin/bash
# ============================================================
# eventOS Agent Fleet — One-Click GCloud Setup + Deploy
# All Things Agentic Hackathon · studio0x
# ============================================================
# Usage: ./setup.sh
# Automates: project creation, API enablement, secret storage, deploy
# Prerequisites: gcloud CLI installed, logged in (gcloud auth login)
# ============================================================

set -euo pipefail

# ─── Color helpers ──────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok() { echo -e "${GREEN}✓${RESET} $1"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $1"; }
err() { echo -e "${RED}✗${RESET} $1"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}── $1${RESET}"; }
banner() {
  echo -e "\n${CYAN}╔══════════════════════════════════════════════════╗"
  echo -e "║   eventOS Agent Fleet — Cloud Run Setup          ║"
  echo -e "║   All Things Agentic Hackathon · studio0x        ║"
  echo -e "╚══════════════════════════════════════════════════╝${RESET}\n"
}

banner

# ─── Step 0: Check prerequisites ────────────────────────────
step "Checking prerequisites"

if ! command -v gcloud &>/dev/null; then
  err "gcloud not found. Install: brew install --cask google-cloud-sdk"
fi
ok "gcloud found: $(gcloud version --format='value(Google Cloud SDK)')"

if ! command -v docker &>/dev/null; then
  warn "Docker not found — needed for local testing. Cloud Run deploy will still work."
else
  ok "Docker found"
fi

# Check gcloud auth
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)
if [[ -z "$ACTIVE_ACCOUNT" ]]; then
  warn "Not logged in. Running gcloud auth login..."
  gcloud auth login
  gcloud auth application-default login
fi
ok "Authenticated as: $ACTIVE_ACCOUNT"

# ─── Step 1: Project setup ──────────────────────────────────
step "Project setup"

TIMESTAMP=$(date +%s)
DEFAULT_PROJECT="eventos-fleet-$TIMESTAMP"

echo -e "${BOLD}Enter GCP Project ID${RESET} (or press Enter for: $DEFAULT_PROJECT):"
read -r PROJECT_INPUT
PROJECT_ID="${PROJECT_INPUT:-$DEFAULT_PROJECT}"

# Check if project exists
if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  ok "Using existing project: $PROJECT_ID"
else
  echo "Creating project: $PROJECT_ID..."
  gcloud projects create "$PROJECT_ID" --name="eventOS Agent Fleet" || {
    warn "Project creation failed — may already exist or require billing. Continuing..."
  }
  ok "Project created: $PROJECT_ID"
fi

gcloud config set project "$PROJECT_ID"
ok "Active project: $PROJECT_ID"

# ─── Step 2: Billing check ──────────────────────────────────
step "Billing check"

BILLING=$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || echo "false")
if [[ "$BILLING" != "True" ]]; then
  warn "Billing not enabled for $PROJECT_ID"
  echo ""
  echo "  1. Go to: https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
  echo "  2. Link a billing account"
  echo "  3. Come back and press Enter to continue"
  echo ""
  read -r -p "Press Enter when billing is enabled..."
fi
ok "Billing check passed"

# ─── Step 3: Enable APIs ────────────────────────────────────
step "Enabling required APIs (this takes ~60 seconds)"

APIS=(
  "run.googleapis.com"
  "cloudbuild.googleapis.com"
  "secretmanager.googleapis.com"
  "artifactregistry.googleapis.com"
  "containerregistry.googleapis.com"
)

gcloud services enable "${APIS[@]}" --project="$PROJECT_ID"
ok "APIs enabled: ${APIS[*]}"

# ─── Step 4: Gemini API key ─────────────────────────────────
step "Gemini API key setup"

SECRET_NAME="gemini-api-key"

# Check if secret already exists
if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
  ok "Secret '$SECRET_NAME' already exists — skipping"
else
  echo ""
  echo -e "  Get your key at: ${CYAN}https://aistudio.google.com/apikey${RESET}"
  echo -e "  ${BOLD}Paste your Gemini API key:${RESET}"
  read -r -s GEMINI_KEY

  if [[ -z "$GEMINI_KEY" ]]; then
    err "No API key provided. Cannot continue."
  fi

  echo -n "$GEMINI_KEY" | gcloud secrets create "$SECRET_NAME" \
    --data-file=- \
    --replication-policy=automatic \
    --project="$PROJECT_ID"
  ok "Secret stored in Secret Manager"

  # Also write to .env.local for local dev (never committed)
  echo "GEMINI_API_KEY=$GEMINI_KEY" > .env.local
  echo "" >> .env.local
  ok ".env.local written for local development"
fi

# ─── Step 5: Deploy to Cloud Run ────────────────────────────
step "Deploying to Cloud Run"

export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
export SERVICE_NAME="${SERVICE_NAME:-eventos-agent-fleet}"

# Grant Cloud Run access to the secret
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  2>/dev/null || warn "IAM binding already exists — continuing"

ok "IAM permissions configured"

# Run the deploy script
chmod +x deploy.sh
./deploy.sh

# ─── Step 6: Verify ─────────────────────────────────────────
step "Verifying deployment"

# Get the deployed URL
FLEET_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region="$GOOGLE_CLOUD_REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)' 2>/dev/null || echo "")

if [[ -z "$FLEET_URL" ]]; then
  warn "Could not auto-detect URL. Check: gcloud run services list"
else
  ok "Fleet deployed at: $FLEET_URL"

  echo ""
  echo "Verifying endpoints..."
  sleep 3

  # Health check
  if curl -sf "$FLEET_URL/health" &>/dev/null; then
    ok "Health check passed: $FLEET_URL/health"
  else
    warn "Health check failed — service may still be starting. Try in 30 seconds."
  fi

  # ─── Step 7: Print summary ──────────────────────────────────
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}║  ${GREEN}${BOLD}DEPLOYMENT COMPLETE${RESET}${CYAN}                                   ║${RESET}"
  echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${RESET}"
  echo -e "${CYAN}║${RESET}  Project:     $PROJECT_ID"
  echo -e "${CYAN}║${RESET}  Fleet URL:   ${BOLD}$FLEET_URL${RESET}"
  echo -e "${CYAN}║${RESET}"
  echo -e "${CYAN}║${RESET}  Endpoints:"
  echo -e "${CYAN}║${RESET}    $FLEET_URL/ui          ← Agent Registry (for judges)"
  echo -e "${CYAN}║${RESET}    $FLEET_URL/agents       ← JSON registry"
  echo -e "${CYAN}║${RESET}    $FLEET_URL/demo/conflict ← Booking demo"
  echo -e "${CYAN}║${RESET}    $FLEET_URL/demo/insight  ← Insight demo"
  echo -e "${CYAN}║${RESET}    $FLEET_URL/docs          ← API docs"
  echo -e "${CYAN}║${RESET}"
  echo -e "${CYAN}║${RESET}  Next steps:"
  echo -e "${CYAN}║${RESET}    1. Open $FLEET_URL/ui in your browser"
  echo -e "${CYAN}║${RESET}    2. Record your demo video (QuickTime → New Screen Recording)"
  echo -e "${CYAN}║${RESET}    3. Push to GitHub: gh repo create hackathon-agentic --public"
  echo -e "${CYAN}║${RESET}    4. Submit at https://allthingsagentichackathon.devpost.com"
  echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${RESET}"
  echo ""

  # Save the URL for easy reference
  echo "$FLEET_URL" > .fleet-url
  ok "URL saved to .fleet-url for easy reference"
fi

#!/bin/bash
# Deploy eventOS Agent Fleet to Google Cloud Run
# Prerequisites: gcloud CLI installed + authenticated, Docker running

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"eventos-fleet-1788055076"}
REGION=${GOOGLE_CLOUD_REGION:-"us-central1"}
SERVICE_NAME="eventos-agent-fleet"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying eventOS Agent Fleet to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service: $SERVICE_NAME"

# Build and push image
echo "📦 Building Docker image..."
gcloud builds submit --tag "$IMAGE" .

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_MODEL=gemini-2.0-flash" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --port 8080

echo "✅ Deployed! Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format "value(status.url)"

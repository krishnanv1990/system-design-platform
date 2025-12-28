#!/bin/bash
# Deploy System Design Platform to Production Environment
# Deploys both backend and frontend to Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT="system-design-platform-prod"
REGION="us-central1"
BACKEND_SERVICE="sdp-backend"
FRONTEND_SERVICE="sdp-frontend"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== Deploying to Production ===${NC}"
echo "Project: $PROJECT"
echo "Region: $REGION"
echo ""

# Set the project
gcloud config set project $PROJECT

# Get Cloud SQL connection name
echo -e "${YELLOW}Getting Cloud SQL connection info...${NC}"
CLOUD_SQL_CONNECTION=$(gcloud sql instances describe sdp-db-prod --format='value(connectionName)' 2>/dev/null || echo "")

if [ -z "$CLOUD_SQL_CONNECTION" ]; then
    echo -e "${RED}Error: Cloud SQL instance not found. Run setup-projects.sh first.${NC}"
    exit 1
fi

echo "Cloud SQL: $CLOUD_SQL_CONNECTION"

# ==================== Deploy Backend ====================
echo ""
echo -e "${BLUE}=== Deploying Backend ===${NC}"

cd "$ROOT_DIR"

# Build and push backend container
echo -e "${YELLOW}Building backend container...${NC}"
gcloud builds submit \
    --tag gcr.io/$PROJECT/$BACKEND_SERVICE \
    --timeout=1200s \
    .

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying backend to Cloud Run...${NC}"
gcloud run deploy $BACKEND_SERVICE \
    --image gcr.io/$PROJECT/$BACKEND_SERVICE \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --add-cloudsql-instances $CLOUD_SQL_CONNECTION \
    --set-secrets "DATABASE_URL=database-url:latest,JWT_SECRET_KEY=jwt-secret:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,GOOGLE_CLIENT_ID=google-client-id:latest,GOOGLE_CLIENT_SECRET=google-client-secret:latest,GITHUB_CLIENT_ID=github-client-id:latest,GITHUB_CLIENT_SECRET=github-client-secret:latest" \
    --set-env-vars "DEMO_MODE=false,DEBUG=false,GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION" \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --timeout 300

# Get backend URL
BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}Backend deployed: $BACKEND_URL${NC}"

# Update backend with frontend URL (will be updated after frontend deployment)
echo ""

# ==================== Deploy Frontend ====================
echo -e "${BLUE}=== Deploying Frontend ===${NC}"

cd "$ROOT_DIR/frontend"

# Build frontend container with backend URL using Cloud Build
echo -e "${YELLOW}Building frontend container with Cloud Build...${NC}"
gcloud builds submit \
    --config=cloudbuild.yaml \
    --timeout=1200s \
    --substitutions=_VITE_API_URL="$BACKEND_URL",_SERVICE_NAME="$FRONTEND_SERVICE" \
    .

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying frontend to Cloud Run...${NC}"
gcloud run deploy $FRONTEND_SERVICE \
    --image gcr.io/$PROJECT/$FRONTEND_SERVICE \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 256Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}Frontend deployed: $FRONTEND_URL${NC}"

# ==================== Update Backend with Frontend URL ====================
echo ""
echo -e "${YELLOW}Updating backend with frontend URL...${NC}"
gcloud run services update $BACKEND_SERVICE \
    --region $REGION \
    --update-env-vars "FRONTEND_URL=$FRONTEND_URL,BACKEND_URL=$BACKEND_URL"

# ==================== Run Database Migrations ====================
echo ""
echo -e "${YELLOW}Running database migrations...${NC}"
echo -e "${YELLOW}Note: Migrations should be run via Cloud SQL Proxy${NC}"
echo ""
echo "To run migrations manually:"
echo "1. Install Cloud SQL Proxy: https://cloud.google.com/sql/docs/postgres/sql-proxy"
echo "2. Run: cloud-sql-proxy $CLOUD_SQL_CONNECTION &"
echo "3. Get database URL: gcloud secrets versions access latest --secret=database-url"
echo "4. Run: cd backend && DATABASE_URL=<url> alembic upgrade head"

# ==================== Summary ====================
echo ""
echo -e "${GREEN}=== Production Deployment Complete ===${NC}"
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL:  $BACKEND_URL"
echo ""
echo -e "${YELLOW}Important: Configure OAuth redirect URIs in:${NC}"
echo "- Google Cloud Console: $BACKEND_URL/api/auth/google/callback"
echo "- GitHub Developer Settings: $BACKEND_URL/api/auth/github/callback"
echo "- Facebook Developer Console: $BACKEND_URL/api/auth/facebook/callback"
echo "- LinkedIn Developer Portal: $BACKEND_URL/api/auth/linkedin/callback"

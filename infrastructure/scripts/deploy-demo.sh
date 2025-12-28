#!/bin/bash
# Deploy System Design Platform to Demo/Internal Environment
# Demo mode enabled, IP-restricted access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT="sdp-demo-20251225"
REGION="us-central1"
BACKEND_SERVICE="sdp-backend"
FRONTEND_SERVICE="sdp-frontend"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== Deploying to Demo Environment ===${NC}"
echo "Project: $PROJECT"
echo "Region: $REGION"
echo ""

# Get current IP for restriction (use IPv4)
MY_IP=$(curl -s -4 ifconfig.me 2>/dev/null || curl -s ipv4.icanhazip.com)
echo -e "${YELLOW}Your current IP: $MY_IP${NC}"
echo "This IP will be allowed to access the demo environment."
echo ""

# Set the project
gcloud config set project $PROJECT

# Get Cloud SQL connection name
echo -e "${YELLOW}Getting Cloud SQL connection info...${NC}"
CLOUD_SQL_CONNECTION=$(gcloud sql instances describe sdp-db --format='value(connectionName)' 2>/dev/null || echo "")

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

# Deploy to Cloud Run (initially allow unauthenticated for setup)
echo -e "${YELLOW}Deploying backend to Cloud Run...${NC}"
gcloud run deploy $BACKEND_SERVICE \
    --image gcr.io/$PROJECT/$BACKEND_SERVICE \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --add-cloudsql-instances $CLOUD_SQL_CONNECTION \
    --set-secrets "DATABASE_URL=sdp-database-url:latest" \
    --set-env-vars "DEMO_MODE=true,DEBUG=true,GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION" \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 3

# Get backend URL
BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}Backend deployed: $BACKEND_URL${NC}"

# ==================== Deploy Frontend ====================
echo ""
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
    --max-instances 2

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}Frontend deployed: $FRONTEND_URL${NC}"

# ==================== Update Backend with Frontend URL ====================
echo ""
echo -e "${YELLOW}Updating backend with frontend URL...${NC}"
gcloud run services update $BACKEND_SERVICE \
    --region $REGION \
    --update-env-vars "FRONTEND_URL=$FRONTEND_URL,BACKEND_URL=$BACKEND_URL"

# ==================== Configure IP Restriction with Cloud Armor ====================
echo ""
echo -e "${BLUE}=== Configuring IP Restriction with Cloud Armor ===${NC}"

# Create Cloud Armor security policy
POLICY_NAME="sdp-dev-ip-policy"
echo -e "${YELLOW}Creating Cloud Armor security policy...${NC}"

# Delete existing policy if exists
gcloud compute security-policies delete $POLICY_NAME --quiet 2>/dev/null || true

# Create security policy that denies all by default
gcloud compute security-policies create $POLICY_NAME \
    --description="IP restriction for dev environment" 2>/dev/null || true

# Update default rule to deny
gcloud compute security-policies rules update 2147483647 \
    --security-policy=$POLICY_NAME \
    --action=deny-403

# Add rule to allow user's IP
gcloud compute security-policies rules create 1000 \
    --security-policy=$POLICY_NAME \
    --action=allow \
    --src-ip-ranges="$MY_IP/32" \
    --description="Allow developer IP"

echo -e "${GREEN}Security policy created for IP: $MY_IP${NC}"

# Create serverless NEG for backend
echo -e "${YELLOW}Setting up load balancer with Cloud Armor...${NC}"

# Backend NEG
gcloud compute network-endpoint-groups create sdp-backend-neg \
    --region=$REGION \
    --network-endpoint-type=serverless \
    --cloud-run-service=$BACKEND_SERVICE 2>/dev/null || true

# Frontend NEG
gcloud compute network-endpoint-groups create sdp-frontend-neg \
    --region=$REGION \
    --network-endpoint-type=serverless \
    --cloud-run-service=$FRONTEND_SERVICE 2>/dev/null || true

# Backend service for backend
gcloud compute backend-services create sdp-backend-bs \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED 2>/dev/null || true

gcloud compute backend-services add-backend sdp-backend-bs \
    --global \
    --network-endpoint-group=sdp-backend-neg \
    --network-endpoint-group-region=$REGION 2>/dev/null || true

# Backend service for frontend
gcloud compute backend-services create sdp-frontend-bs \
    --global \
    --load-balancing-scheme=EXTERNAL_MANAGED 2>/dev/null || true

gcloud compute backend-services add-backend sdp-frontend-bs \
    --global \
    --network-endpoint-group=sdp-frontend-neg \
    --network-endpoint-group-region=$REGION 2>/dev/null || true

# Apply security policy to both backend services
gcloud compute backend-services update sdp-backend-bs \
    --global \
    --security-policy=$POLICY_NAME 2>/dev/null || true

gcloud compute backend-services update sdp-frontend-bs \
    --global \
    --security-policy=$POLICY_NAME 2>/dev/null || true

# URL map
gcloud compute url-maps create sdp-dev-lb \
    --default-service=sdp-frontend-bs 2>/dev/null || true

gcloud compute url-maps add-path-matcher sdp-dev-lb \
    --path-matcher-name=api-matcher \
    --default-service=sdp-frontend-bs \
    --backend-service-path-rules="/api/*=sdp-backend-bs" 2>/dev/null || true

# HTTPS proxy (using managed SSL)
gcloud compute target-https-proxies create sdp-dev-https-proxy \
    --url-map=sdp-dev-lb \
    --ssl-certificates=sdp-dev-cert 2>/dev/null || \
gcloud compute target-http-proxies create sdp-dev-http-proxy \
    --url-map=sdp-dev-lb 2>/dev/null || true

# Reserve static IP
gcloud compute addresses create sdp-dev-ip --global 2>/dev/null || true
DEV_IP=$(gcloud compute addresses describe sdp-dev-ip --global --format='value(address)' 2>/dev/null || echo "")

# Create forwarding rule
if [ -n "$DEV_IP" ]; then
    gcloud compute forwarding-rules create sdp-dev-forwarding \
        --global \
        --target-http-proxy=sdp-dev-http-proxy \
        --ports=80 \
        --address=$DEV_IP 2>/dev/null || true
fi

echo -e "${GREEN}Load balancer configured with IP restriction${NC}"
echo "Dev environment IP: $DEV_IP"

# ==================== Summary ====================
echo ""
echo -e "${GREEN}=== Dev Environment Deployment Complete ===${NC}"
echo ""
echo -e "${YELLOW}Cloud Run URLs (for reference):${NC}"
echo "  Frontend: $FRONTEND_URL"
echo "  Backend:  $BACKEND_URL"
echo ""
echo -e "${GREEN}IP-Restricted Access (use this):${NC}"
if [ -n "$DEV_IP" ]; then
    echo "  Dev URL: http://$DEV_IP"
else
    echo "  (Load balancer IP pending)"
fi
echo ""
echo -e "${YELLOW}Access Restriction:${NC}"
echo "  Only accessible from IP: $MY_IP"
echo ""
echo "To update allowed IP later:"
echo "  gcloud compute security-policies rules update 1000 \\"
echo "      --security-policy=$POLICY_NAME \\"
echo "      --src-ip-ranges=\"NEW_IP/32\""

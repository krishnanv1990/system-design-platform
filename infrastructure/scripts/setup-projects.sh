#!/bin/bash
# Setup GCP projects and enable required APIs for System Design Platform
# This script creates both production and demo environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project names
PROD_PROJECT="system-design-platform-prod"
DEMO_PROJECT="system-design-platform-demo"
REGION="us-central1"

echo -e "${GREEN}=== System Design Platform - GCP Setup ===${NC}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed. Please install it first.${NC}"
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null 2>&1; then
    echo -e "${YELLOW}Please authenticate with GCP:${NC}"
    gcloud auth login
fi

# Get billing account
echo -e "${YELLOW}Available billing accounts:${NC}"
gcloud billing accounts list

echo ""
read -p "Enter your billing account ID: " BILLING_ACCOUNT

if [ -z "$BILLING_ACCOUNT" ]; then
    echo -e "${RED}Error: Billing account ID is required${NC}"
    exit 1
fi

# Function to create a project
create_project() {
    local PROJECT_ID=$1
    local PROJECT_NAME=$2

    echo -e "${YELLOW}Creating project: $PROJECT_ID${NC}"

    # Check if project exists
    if gcloud projects describe $PROJECT_ID &> /dev/null; then
        echo -e "${GREEN}Project $PROJECT_ID already exists${NC}"
    else
        gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"
        echo -e "${GREEN}Created project: $PROJECT_ID${NC}"
    fi

    # Link billing account
    echo "Linking billing account..."
    gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT

    # Enable APIs
    echo "Enabling APIs..."
    gcloud services enable --project=$PROJECT_ID \
        run.googleapis.com \
        sqladmin.googleapis.com \
        secretmanager.googleapis.com \
        artifactregistry.googleapis.com \
        cloudbuild.googleapis.com \
        compute.googleapis.com \
        storage.googleapis.com \
        containerregistry.googleapis.com

    echo -e "${GREEN}APIs enabled for $PROJECT_ID${NC}"
}

# Function to create Cloud SQL instance
create_database() {
    local PROJECT_ID=$1
    local INSTANCE_NAME=$2
    local TIER=$3

    echo -e "${YELLOW}Creating Cloud SQL instance: $INSTANCE_NAME${NC}"

    # Check if instance exists
    if gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID &> /dev/null; then
        echo -e "${GREEN}Cloud SQL instance $INSTANCE_NAME already exists${NC}"
    else
        gcloud sql instances create $INSTANCE_NAME \
            --database-version=POSTGRES_15 \
            --tier=$TIER \
            --region=$REGION \
            --root-password=$(openssl rand -base64 24) \
            --project=$PROJECT_ID

        echo -e "${GREEN}Created Cloud SQL instance: $INSTANCE_NAME${NC}"
    fi

    # Create database
    echo "Creating database..."
    gcloud sql databases create system_design_db \
        --instance=$INSTANCE_NAME \
        --project=$PROJECT_ID 2>/dev/null || echo "Database may already exist"

    # Create app user
    APP_PASSWORD=$(openssl rand -base64 24)
    echo "Creating database user..."
    gcloud sql users create sdp_user \
        --instance=$INSTANCE_NAME \
        --password=$APP_PASSWORD \
        --project=$PROJECT_ID 2>/dev/null || echo "User may already exist"

    # Get connection name
    CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID --format='value(connectionName)')

    # Store database URL in Secret Manager
    DATABASE_URL="postgresql://sdp_user:${APP_PASSWORD}@/${system_design_db}?host=/cloudsql/${CONNECTION_NAME}"

    echo "Storing database URL in Secret Manager..."
    echo -n "$DATABASE_URL" | gcloud secrets create database-url \
        --data-file=- \
        --project=$PROJECT_ID 2>/dev/null || \
    echo -n "$DATABASE_URL" | gcloud secrets versions add database-url \
        --data-file=- \
        --project=$PROJECT_ID

    echo -e "${GREEN}Database setup complete for $PROJECT_ID${NC}"
}

# Function to create secrets
create_secrets() {
    local PROJECT_ID=$1

    echo -e "${YELLOW}Creating secrets for $PROJECT_ID${NC}"

    # JWT Secret
    JWT_SECRET=$(openssl rand -hex 32)
    echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret \
        --data-file=- \
        --project=$PROJECT_ID 2>/dev/null || \
    echo -n "$JWT_SECRET" | gcloud secrets versions add jwt-secret \
        --data-file=- \
        --project=$PROJECT_ID

    # Anthropic API Key placeholder
    if [ "$PROJECT_ID" == "$PROD_PROJECT" ]; then
        echo ""
        read -p "Enter your Anthropic API Key (or press Enter to skip): " ANTHROPIC_KEY
        if [ -n "$ANTHROPIC_KEY" ]; then
            echo -n "$ANTHROPIC_KEY" | gcloud secrets create anthropic-api-key \
                --data-file=- \
                --project=$PROJECT_ID 2>/dev/null || \
            echo -n "$ANTHROPIC_KEY" | gcloud secrets versions add anthropic-api-key \
                --data-file=- \
                --project=$PROJECT_ID
        else
            echo -n "demo-key" | gcloud secrets create anthropic-api-key \
                --data-file=- \
                --project=$PROJECT_ID 2>/dev/null || true
        fi
    else
        # Demo project uses demo key
        echo -n "demo-key" | gcloud secrets create anthropic-api-key \
            --data-file=- \
            --project=$PROJECT_ID 2>/dev/null || true
    fi

    echo -e "${GREEN}Secrets created for $PROJECT_ID${NC}"
}

# Function to grant Cloud Run access to secrets
grant_secret_access() {
    local PROJECT_ID=$1

    echo -e "${YELLOW}Granting Cloud Run access to secrets...${NC}"

    # Get the Cloud Run service account
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
    SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

    for SECRET in database-url jwt-secret anthropic-api-key; do
        gcloud secrets add-iam-policy-binding $SECRET \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --project=$PROJECT_ID 2>/dev/null || true
    done

    echo -e "${GREEN}Secret access granted${NC}"
}

echo ""
echo -e "${GREEN}=== Creating Production Environment ===${NC}"
create_project $PROD_PROJECT "System Design Platform (Prod)"
create_database $PROD_PROJECT "sdp-db-prod" "db-f1-micro"
create_secrets $PROD_PROJECT
grant_secret_access $PROD_PROJECT

echo ""
echo -e "${GREEN}=== Creating Demo Environment ===${NC}"
create_project $DEMO_PROJECT "System Design Platform (Demo)"
create_database $DEMO_PROJECT "sdp-db-demo" "db-f1-micro"
create_secrets $DEMO_PROJECT
grant_secret_access $DEMO_PROJECT

echo ""
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""
echo "Next steps:"
echo "1. Run: ./deploy-prod.sh    # Deploy production environment"
echo "2. Run: ./deploy-demo.sh    # Deploy demo environment"
echo ""
echo "Production project: $PROD_PROJECT"
echo "Demo project: $DEMO_PROJECT"

#!/bin/bash
# Update IP allowlist for demo environment
# Run this whenever your IP address changes

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

echo -e "${GREEN}=== Update Demo Environment Access ===${NC}"
echo ""

# Get current IP
MY_IP=$(curl -s ifconfig.me)
echo -e "${YELLOW}Your current IP: $MY_IP${NC}"
echo ""

# Set the project
gcloud config set project $PROJECT

# Get current user email
USER_EMAIL=$(gcloud config get-value account)
echo "Your GCP account: $USER_EMAIL"
echo ""

# Check mode
MODE=${1:-iam}

if [ "$MODE" == "iam" ]; then
    echo -e "${BLUE}=== IAM-Based Access Control ===${NC}"
    echo ""

    # Check current IAM policy
    echo -e "${YELLOW}Current access policy:${NC}"
    gcloud run services get-iam-policy $FRONTEND_SERVICE --region=$REGION --format='table(bindings.members,bindings.role)' 2>/dev/null || echo "No policy found"
    echo ""

    read -p "Update access to only allow your account? (y/n): " CONFIRM

    if [ "$CONFIRM" == "y" ] || [ "$CONFIRM" == "Y" ]; then
        # Remove allUsers if present
        echo -e "${YELLOW}Removing public access...${NC}"
        gcloud run services remove-iam-policy-binding $FRONTEND_SERVICE \
            --region=$REGION \
            --member="allUsers" \
            --role="roles/run.invoker" 2>/dev/null || true

        gcloud run services remove-iam-policy-binding $BACKEND_SERVICE \
            --region=$REGION \
            --member="allUsers" \
            --role="roles/run.invoker" 2>/dev/null || true

        # Add current user
        echo -e "${YELLOW}Adding your account...${NC}"
        gcloud run services add-iam-policy-binding $FRONTEND_SERVICE \
            --region=$REGION \
            --member="user:$USER_EMAIL" \
            --role="roles/run.invoker"

        gcloud run services add-iam-policy-binding $BACKEND_SERVICE \
            --region=$REGION \
            --member="user:$USER_EMAIL" \
            --role="roles/run.invoker"

        echo -e "${GREEN}Access restricted to: $USER_EMAIL${NC}"
    fi

elif [ "$MODE" == "public" ]; then
    echo -e "${BLUE}=== Making Demo Public ===${NC}"
    echo ""

    read -p "Make demo environment publicly accessible? (y/n): " CONFIRM

    if [ "$CONFIRM" == "y" ] || [ "$CONFIRM" == "Y" ]; then
        gcloud run services add-iam-policy-binding $FRONTEND_SERVICE \
            --region=$REGION \
            --member="allUsers" \
            --role="roles/run.invoker"

        gcloud run services add-iam-policy-binding $BACKEND_SERVICE \
            --region=$REGION \
            --member="user:$USER_EMAIL" \
            --role="roles/run.invoker"

        echo -e "${GREEN}Demo environment is now public${NC}"
    fi

elif [ "$MODE" == "add" ]; then
    echo -e "${BLUE}=== Add Additional User ===${NC}"
    echo ""

    read -p "Enter email to add: " NEW_EMAIL

    if [ -n "$NEW_EMAIL" ]; then
        gcloud run services add-iam-policy-binding $FRONTEND_SERVICE \
            --region=$REGION \
            --member="user:$NEW_EMAIL" \
            --role="roles/run.invoker"

        gcloud run services add-iam-policy-binding $BACKEND_SERVICE \
            --region=$REGION \
            --member="user:$NEW_EMAIL" \
            --role="roles/run.invoker"

        echo -e "${GREEN}Added access for: $NEW_EMAIL${NC}"
    fi

else
    echo "Usage: $0 [iam|public|add]"
    echo ""
    echo "Commands:"
    echo "  iam     - Restrict access to your Google account only (default)"
    echo "  public  - Make demo publicly accessible"
    echo "  add     - Add another user to the allowlist"
    echo ""
fi

# Show URLs
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE --region=$REGION --format='value(status.url)' 2>/dev/null || echo "Not deployed")
BACKEND_URL=$(gcloud run services describe $BACKEND_SERVICE --region=$REGION --format='value(status.url)' 2>/dev/null || echo "Not deployed")

echo ""
echo -e "${GREEN}=== Demo Environment URLs ===${NC}"
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo ""
echo "To access (if IAM restricted):"
echo "1. Open URL in browser"
echo "2. Sign in with your Google account when prompted"

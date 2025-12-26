# Deployment Guide

This guide covers deploying the System Design Interview Platform to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [GCP Deployment](#gcp-deployment)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Monitoring](#monitoring)

## Prerequisites

### Required Software

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)
- Terraform 1.6+ (for GCP deployment features)
- Google Cloud SDK (for GCP deployment)

### Required Accounts & Keys

1. **Google OAuth Credentials**
   - Create at [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Add authorized redirect URIs for your domains

2. **Anthropic API Key**
   - Get from [Anthropic Console](https://console.anthropic.com/)

3. **GCP Service Account**
   - Create with required permissions for deployment features

## Local Development

### 1. Clone and Configure

```bash
git clone https://github.com/krishnanv1990/system-design-platform.git
cd system-design-platform
cp .env.example .env
# Edit .env with your credentials
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start database and Redis
docker-compose up -d db redis

# Run migrations (tables auto-created on startup)
python -c "from backend.database import engine, Base; Base.metadata.create_all(bind=engine)"

# Seed sample data
python backend/seed_data.py

# Start backend
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Access the application:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Docker Deployment

### Development Mode

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Seed data
docker-compose exec backend python backend/seed_data.py
```

### Production Mode

Create a production docker-compose file:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - DEBUG=false
    env_file:
      - .env.prod
    depends_on:
      - db
      - redis
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    depends_on:
      - backend
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    restart: always

volumes:
  postgres_data:
  redis_data:
```

Create production frontend Dockerfile:

```dockerfile
# frontend/Dockerfile.prod
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## GCP Deployment

### Option 1: Cloud Run (Recommended)

#### Backend Deployment

```bash
# Build and push backend image
gcloud builds submit --tag gcr.io/${PROJECT_ID}/sdp-backend .

# Deploy to Cloud Run
gcloud run deploy sdp-backend \
  --image gcr.io/${PROJECT_ID}/sdp-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=${DATABASE_URL}" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-key:latest,JWT_SECRET_KEY=jwt-secret:latest"
```

#### Frontend Deployment

```bash
cd frontend

# Build production bundle
npm run build

# Deploy to Cloud Storage + CDN
gsutil -m cp -r dist/* gs://${BUCKET_NAME}/

# Configure Cloud CDN
gcloud compute backend-buckets create sdp-frontend \
  --gcs-bucket-name=${BUCKET_NAME} \
  --enable-cdn
```

### Option 2: GKE (Kubernetes)

Create Kubernetes manifests:

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sdp-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sdp-backend
  template:
    metadata:
      labels:
        app: sdp-backend
    spec:
      containers:
      - name: backend
        image: gcr.io/${PROJECT_ID}/sdp-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: sdp-backend
spec:
  selector:
    app: sdp-backend
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

Deploy:

```bash
# Create cluster
gcloud container clusters create sdp-cluster \
  --zone us-central1-a \
  --num-nodes 3

# Apply manifests
kubectl apply -f k8s/
```

## Environment Configuration

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | JWT signing key | Random 32+ char string |
| `GOOGLE_CLIENT_ID` | OAuth client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | OAuth secret | `GOCSPX-xxx` |
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-xxx` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `GCP_PROJECT_ID` | GCP project for deployments | - |
| `GCP_REGION` | GCP region | `us-central1` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:5173` |
| `BACKEND_URL` | Backend URL for OAuth redirect | `http://localhost:8000` |

### Production Environment File

```env
# .env.prod
DEBUG=false
APP_NAME=System Design Platform

# Database (use Cloud SQL)
DATABASE_URL=postgresql://user:password@/dbname?host=/cloudsql/project:region:instance

# Authentication
GOOGLE_CLIENT_ID=your-production-client-id
GOOGLE_CLIENT_SECRET=your-production-secret
JWT_SECRET_KEY=your-production-jwt-secret
JWT_EXPIRE_MINUTES=1440

# AI
ANTHROPIC_API_KEY=your-anthropic-key

# GCP
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1

# URLs
FRONTEND_URL=https://your-domain.com
BACKEND_URL=https://api.your-domain.com
```

## Database Setup

### Cloud SQL (Recommended for Production)

```bash
# Create instance
gcloud sql instances create sdp-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create system_design_db --instance=sdp-db

# Create user
gcloud sql users create sdp_user \
  --instance=sdp-db \
  --password=your-secure-password
```

### Database Migrations

The application auto-creates tables on startup. For manual migrations:

```bash
# Using Alembic (if configured)
alembic upgrade head

# Or manually
python -c "from backend.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

### Seed Data

```bash
python backend/seed_data.py
```

## SSL/TLS Configuration

### Using Let's Encrypt with Nginx

```nginx
# nginx.conf
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://frontend:80;
    }

    # Backend API
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Using Cloud Run (Automatic SSL)

Cloud Run automatically provisions SSL certificates for your custom domains.

```bash
gcloud run domain-mappings create \
  --service=sdp-backend \
  --domain=api.your-domain.com \
  --region=us-central1
```

## Monitoring

### Health Checks

The backend exposes health check endpoints:

- `/health` - Basic health check
- `/` - Root endpoint with version info

### Logging

Configure structured logging for production:

```python
# Add to backend/main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### GCP Monitoring

```bash
# Enable Cloud Monitoring
gcloud services enable monitoring.googleapis.com

# Create uptime check
gcloud monitoring uptime-check-configs create sdp-backend-health \
  --display-name="SDP Backend Health" \
  --monitored-resource-type="uptime_url" \
  --http-check-path="/health"
```

### Alerts

```bash
# Create alert policy for high error rate
gcloud alpha monitoring policies create \
  --display-name="High Error Rate" \
  --condition-display-name="Error rate > 1%" \
  --condition-filter="metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\"" \
  --notification-channels="projects/${PROJECT_ID}/notificationChannels/${CHANNEL_ID}"
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check `DATABASE_URL` format
   - Ensure database is accessible
   - Check firewall rules

2. **OAuth Redirect Error**
   - Verify redirect URI matches Google Console
   - Check `BACKEND_URL` configuration

3. **AI Features Not Working**
   - Verify `ANTHROPIC_API_KEY` is valid
   - Check API rate limits

4. **GCP Deployment Fails**
   - Verify service account permissions
   - Check `GCP_CREDENTIALS_PATH`

### Useful Commands

```bash
# View backend logs
docker-compose logs -f backend

# Check database connection
docker-compose exec backend python -c "from backend.database import engine; engine.connect()"

# Test API
curl http://localhost:8000/health

# Rebuild containers
docker-compose up -d --build
```

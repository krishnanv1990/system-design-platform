# Deployment Optimization Guide

This document explains how we optimized deployment time from **minutes to seconds**.

## The Problem

Traditional Terraform-based deployment is too slow for an interactive interview platform:

| Resource | Typical Provision Time |
|----------|----------------------|
| Cloud SQL | 5-10 minutes |
| GKE Cluster | 10-15 minutes |
| VPC Network | 2-3 minutes |
| Cloud Run | 30-60 seconds |

**Total: 10-20+ minutes per candidate** - unacceptable for a practice platform.

## The Solution: Pre-provisioned + Dynamic Deployment

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     PRE-PROVISIONED INFRASTRUCTURE                        │
│                        (Set up once, shared by all)                       │
│                                                                           │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│   │   Cloud SQL     │  │     Redis       │  │    Pub/Sub      │         │
│   │   (Shared DB)   │  │   (Shared)      │  │   (Shared)      │         │
│   │                 │  │                 │  │                 │         │
│   │  ┌───────────┐  │  │  Prefix-based   │  │  Topic-based    │         │
│   │  │ Schema A  │  │  │  isolation:     │  │  isolation:     │         │
│   │  │ Schema B  │  │  │  sub:1:*        │  │  sub-1-events   │         │
│   │  │ Schema C  │  │  │  sub:2:*        │  │  sub-2-events   │         │
│   │  └───────────┘  │  │  sub:3:*        │  │  sub-3-events   │         │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    GKE Cluster (Optional)                        │   │
│   │   Pre-pulled images, ready for instant pod scheduling            │   │
│   └─────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Candidates deploy HERE
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      DYNAMIC DEPLOYMENT LAYER                             │
│                        (Per candidate, fast)                              │
│                                                                           │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                │
│   │  Cloud Run   │   │  Cloud Run   │   │  Cloud Run   │                │
│   │  Service A   │   │  Service B   │   │  Service C   │                │
│   │  (Sub #1)    │   │  (Sub #2)    │   │  (Sub #3)    │                │
│   │              │   │              │   │              │                │
│   │  Deploy: 15s │   │  Deploy: 15s │   │  Deploy: 15s │                │
│   └──────────────┘   └──────────────┘   └──────────────┘                │
│                                                                           │
│   Each service gets:                                                      │
│   - Unique database schema (candidate_123)                               │
│   - Redis key prefix (sub:123:)                                          │
│   - Own Cloud Run URL                                                    │
│   - Resource limits (CPU, memory)                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

## Deployment Strategies Comparison

| Strategy | Deploy Time | Cost | Isolation | Use Case |
|----------|------------|------|-----------|----------|
| **Simulation** | < 1 sec | Free | N/A | Development, unit tests |
| **Cloud Run** | 10-30 sec | Low | Good | Production (recommended) |
| **Kubernetes** | 5-15 sec | Medium | Excellent | High volume, enterprise |
| **Terraform** | 5-15 min | High | Complete | Full infrastructure demo |

## Implementation Details

### 1. Pre-provisioned Infrastructure Setup

Run this once to set up shared infrastructure:

```bash
# Create shared Cloud SQL instance
gcloud sql instances create sdp-shared-db \
  --database-version=POSTGRES_15 \
  --tier=db-g1-small \
  --region=us-central1

# Create shared Redis (Memorystore)
gcloud redis instances create sdp-shared-redis \
  --size=1 \
  --region=us-central1

# Create GKE cluster (optional, for K8s strategy)
gcloud container clusters create sdp-cluster \
  --zone=us-central1-a \
  --num-nodes=3 \
  --machine-type=e2-medium
```

### 2. Dynamic Deployment Flow

```python
# Candidate submits solution
submission = create_submission(...)

# Instead of Terraform (slow):
# terraform_service.deploy(...)  # 10+ minutes

# Use fast deployment (fast):
deployment_service = FastDeploymentService()
result = await deployment_service.deploy(
    submission_id=submission.id,
    design_text=submission.design_text,
    problem_type="url_shortener"
)
# Result in ~15 seconds!

print(result)
# {
#     "success": True,
#     "endpoint_url": "https://sdp-sub-123-xxx.run.app",
#     "deployment_time_seconds": 14.5,
#     "resources": {
#         "database_schema": "candidate_123",
#         "redis_prefix": "sub:123:"
#     }
# }
```

### 3. Isolation Mechanisms

#### Database Isolation (Schema-per-candidate)

```sql
-- Each candidate gets their own schema
CREATE SCHEMA candidate_123;

-- Tables are created within their schema
CREATE TABLE candidate_123.urls (...);
CREATE TABLE candidate_123.users (...);

-- Service connects with schema in URL
DATABASE_URL=postgresql://user:pass@host/db?options=-csearch_path=candidate_123
```

#### Redis Isolation (Prefix-based)

```python
# Each candidate's keys are prefixed
redis_prefix = f"sub:{submission_id}:"

# All operations use the prefix
await redis.set(f"{redis_prefix}url:abc123", original_url)
await redis.get(f"{redis_prefix}url:abc123")

# Cleanup is easy
await redis.delete(*await redis.keys(f"{redis_prefix}*"))
```

#### Network Isolation

```yaml
# Cloud Run service with unique identity
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: sdp-sub-123
spec:
  template:
    spec:
      serviceAccountName: candidate-123-sa  # Limited permissions
      containers:
      - image: gcr.io/project/sdp-candidate:123
        env:
        - name: NAMESPACE
          value: "sub-123"
```

### 4. Template-Based Code Generation

For common problem types, we use pre-built templates instead of AI generation:

```
Problem Type        Template Available    Deploy Time
─────────────────────────────────────────────────────
URL Shortener       ✓ Yes                ~12 sec
Rate Limiter        ✓ Yes                ~12 sec
Distributed Cache   ✓ Yes                ~12 sec
Notification System ✓ Yes                ~15 sec
Custom/Unknown      AI Generated         ~25 sec
```

Templates are:
- Pre-tested and working
- Optimized for fast startup
- Connected to shared infrastructure
- Include health checks

### 5. Container Build Optimization

```dockerfile
# Use slim base image
FROM python:3.11-slim

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code last (changes frequently)
COPY main.py .

# Use uvicorn for fast startup
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Cloud Build caches layers, so subsequent builds are faster.

## Cost Optimization

### Cloud Run Pricing

- Pay only when handling requests
- Scale to zero when idle
- ~$0.00002 per request + CPU/memory time

### Estimated Costs

| Usage | Monthly Cost |
|-------|-------------|
| 100 candidates/day | ~$5-10 |
| 500 candidates/day | ~$25-50 |
| 2000 candidates/day | ~$100-200 |

### Cost Controls

```bash
# Set max instances to limit costs
gcloud run services update sdp-sub-123 \
  --max-instances=2

# Set memory limits
gcloud run services update sdp-sub-123 \
  --memory=512Mi
```

## Cleanup Strategy

### Automatic Cleanup

```python
# Clean up after testing completes
async def cleanup_submission(submission_id: int):
    # 1. Delete Cloud Run service
    await deployment_service.cleanup(submission_id, namespace)

    # 2. Drop database schema
    await db.execute(f"DROP SCHEMA IF EXISTS candidate_{submission_id} CASCADE")

    # 3. Clear Redis keys
    keys = await redis.keys(f"sub:{submission_id}:*")
    if keys:
        await redis.delete(*keys)
```

### Scheduled Cleanup

```bash
# Cloud Scheduler job to clean old deployments
gcloud scheduler jobs create http cleanup-old-deployments \
  --schedule="0 2 * * *" \
  --uri="https://api.example.com/admin/cleanup" \
  --http-method=POST
```

## Migration Guide

### From Terraform to Fast Deployment

1. **Set up shared infrastructure** (one-time)
2. **Update orchestrator** to use `FastDeploymentService`
3. **Update problem templates** for common types
4. **Configure cleanup jobs**

```python
# Before (terraform_service.py)
terraform_code = await terraform_service.generate_terraform(...)
result = await terraform_service.apply(workspace)
# Time: 10-15 minutes

# After (deployment_service.py)
result = await deployment_service.deploy(
    submission_id=submission_id,
    design_text=design_text,
    problem_type=problem_type
)
# Time: 10-30 seconds
```

## Monitoring

### Key Metrics

- Deployment success rate
- Average deployment time
- Container cold start latency
- Database connection pool usage

### Alerts

```bash
# Alert if deployment takes too long
gcloud alpha monitoring policies create \
  --display-name="Slow Deployment" \
  --condition="deployment_time > 60s"
```

## Summary

| Metric | Before (Terraform) | After (Cloud Run) |
|--------|-------------------|-------------------|
| Deploy time | 10-15 min | 10-30 sec |
| Cost per deploy | ~$0.50 | ~$0.01 |
| Candidate wait | Unacceptable | Acceptable |
| Complexity | High | Low |

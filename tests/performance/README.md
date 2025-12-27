# Performance Testing Guide

This directory contains performance tests for the URL Shortener service at various scales.

## Test Files

| File | Description | Scale |
|------|-------------|-------|
| `locustfile_url_shortener.py` | Basic performance tests | 10-100 users |
| `locustfile_distributed.py` | Distributed load testing | 1M+ users |
| `kubernetes/locust-deployment.yaml` | K8s deployment for distributed tests | Unlimited |

## Quick Start

### Basic Load Test (Single Machine)

```bash
# Run basic performance test
locust -f locustfile_url_shortener.py --host=http://your-service-url

# Headless mode with 100 users
locust -f locustfile_url_shortener.py \
  --host=http://your-service-url \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m
```

### Distributed Load Test (High Scale)

```bash
# Start master node
locust -f locustfile_distributed.py \
  --master \
  --host=http://your-service-url

# Start worker nodes (run on multiple machines)
locust -f locustfile_distributed.py \
  --worker \
  --master-host=<master-ip>
```

### Kubernetes Distributed Test

```bash
# Deploy Locust to Kubernetes
kubectl apply -f kubernetes/locust-deployment.yaml

# Scale workers for more load
kubectl scale deployment locust-worker --replicas=50

# Access Locust UI
kubectl port-forward svc/locust-master-web 8089:8089
# Open http://localhost:8089
```

## Scale Configurations

### Small Scale (Development)
- **Users**: 10-100
- **RPS**: 10-100
- **Duration**: 1-5 minutes
- **Infrastructure**: Single machine

```bash
locust -f locustfile_url_shortener.py \
  --host=$TARGET_URL \
  --headless \
  --users 50 \
  --spawn-rate 5 \
  --run-time 2m
```

### Medium Scale (Staging)
- **Users**: 1,000-10,000
- **RPS**: 1,000-5,000
- **Duration**: 10-30 minutes
- **Infrastructure**: 2-5 worker machines

```bash
# Master
locust -f locustfile_distributed.py --master --host=$TARGET_URL

# Workers (run on each worker machine)
locust -f locustfile_distributed.py --worker --master-host=$MASTER_IP
```

### Large Scale (Production Simulation)
- **Users**: 100,000-1,000,000
- **RPS**: 10,000-100,000
- **Duration**: 1-4 hours
- **Infrastructure**: Kubernetes cluster with 50-100 worker pods

```bash
# Set environment variables
export TARGET_RPS=100000
export CONCURRENT_USERS=1000000

# Deploy to Kubernetes
kubectl apply -f kubernetes/locust-deployment.yaml
kubectl scale deployment locust-worker --replicas=100
```

## Test Scenarios

### 1. Baseline Performance
Measures normal operation performance.

```bash
locust -f locustfile_url_shortener.py \
  --host=$TARGET_URL \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m
```

### 2. Peak Load Simulation
Simulates peak hour traffic (2-3x normal load).

```bash
locust -f locustfile_distributed.py \
  --host=$TARGET_URL \
  --headless \
  --users 10000 \
  --spawn-rate 500 \
  --run-time 30m
```

### 3. Viral Content Surge
Simulates viral URL getting millions of hits.

```bash
export VIRAL_CODES="abc123,xyz789"
locust -f locustfile_distributed.py \
  --host=$TARGET_URL \
  --headless \
  --users 50000 \
  --spawn-rate 1000 \
  --run-time 15m
```

### 4. Sustained High Load
Tests system stability under extended load.

```bash
locust -f locustfile_distributed.py \
  --host=$TARGET_URL \
  --headless \
  --users 100000 \
  --spawn-rate 5000 \
  --run-time 4h
```

### 5. Burst Traffic
Simulates sudden traffic spikes.

Uses `StagesLoadShape` in `locustfile_distributed.py`:
- Warm-up → Normal → Peak → Sustained Peak → Cool-down

## Performance Thresholds

| Metric | Acceptable | Warning | Critical |
|--------|-----------|---------|----------|
| P50 Latency | <100ms | <500ms | >1000ms |
| P95 Latency | <500ms | <1000ms | >2000ms |
| P99 Latency | <1000ms | <2000ms | >5000ms |
| Error Rate | <1% | <5% | >10% |
| Availability | >99.9% | >99% | <99% |

## Expected Results at Scale

### 1 Million Concurrent Users

Target service configuration:
- **Cloud Run**: 500 min instances, 2000 max instances
- **Database**: Cloud SQL with read replicas or Spanner
- **Cache**: Redis Cluster (6+ nodes)
- **CDN**: Cloud CDN for static/cacheable responses

Expected results:
```
Requests/sec:       ~100,000
Median Latency:     ~50ms
P95 Latency:        ~200ms
P99 Latency:        ~500ms
Error Rate:         <0.5%
```

### 1 Billion URLs

Storage requirements:
- **URL Storage**: ~100GB (100 bytes/URL average)
- **Index Storage**: ~50GB
- **Cache**: ~10GB (hot URLs)

Write capacity:
- Peak: 10,000 writes/second
- Sustained: 1,000 writes/second

Read capacity:
- Peak: 500,000 reads/second
- Sustained: 100,000 reads/second

## Monitoring During Tests

### Metrics to Watch

1. **Application Metrics**
   - Request latency (p50, p95, p99)
   - Error rate
   - Request throughput (RPS)

2. **Infrastructure Metrics**
   - CPU utilization
   - Memory usage
   - Network I/O
   - Disk I/O

3. **Database Metrics**
   - Query latency
   - Connection pool usage
   - Replication lag

4. **Cache Metrics**
   - Hit rate
   - Memory usage
   - Eviction rate

### Grafana Dashboard

Import the following queries for monitoring:

```promql
# Request Rate
sum(rate(http_requests_total[5m]))

# Error Rate
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# P95 Latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Active Connections
sum(http_server_active_requests)
```

## Troubleshooting

### High Latency
1. Check database query performance
2. Verify cache hit rate (should be >90%)
3. Check for instance CPU throttling
4. Review network latency between services

### High Error Rate
1. Check application logs for errors
2. Verify database connection limits
3. Check for rate limiting triggers
4. Review circuit breaker status

### Test Client Bottleneck
1. Add more Locust workers
2. Increase worker CPU/memory
3. Check network bandwidth on workers
4. Distribute workers across regions

## CI/CD Integration

Add to your pipeline:

```yaml
performance-test:
  stage: test
  script:
    - pip install locust
    - locust -f tests/performance/locustfile_url_shortener.py \
        --host=$STAGING_URL \
        --headless \
        --users 100 \
        --spawn-rate 10 \
        --run-time 5m \
        --csv=results
    - python scripts/validate_perf_results.py results_stats.csv
  artifacts:
    paths:
      - results_*.csv
```

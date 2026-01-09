# Audit and Security

This document describes the audit logging and security features of the System Design Platform.

## Audit Logging

All significant events are logged for compliance and debugging.

### Logged Events

| Event Type | Description | Data Captured |
|------------|-------------|---------------|
| `auth.login` | User login | user_id, provider, ip |
| `auth.logout` | User logout | user_id |
| `auth.failed` | Failed auth attempt | ip, reason |
| `submission.created` | New submission | user_id, problem_id |
| `submission.completed` | Submission finished | submission_id, status |
| `deployment.created` | GCP deployment | submission_id, resources |
| `deployment.destroyed` | Cleanup | submission_id |
| `admin.action` | Admin operation | admin_id, action, target |
| `system.error` | System error | service, error, stack |

### Audit Log Schema

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,
  user_id UUID REFERENCES users(id),
  ip_address INET,
  user_agent TEXT,
  data JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_event ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

### Querying Audit Logs

```python
# Get recent failed logins
logs = await AuditService.query(
    event_type="auth.failed",
    since=datetime.now() - timedelta(hours=1)
)

# Get user activity
logs = await AuditService.query(
    user_id=user_id,
    limit=100
)
```

### API Endpoints

```
GET /api/user/activity          # Get own activity log
GET /api/admin/activity         # Admin: Get all activity
```

## Security Measures

### Authentication

- **OAuth 2.0** with Google, GitHub, LinkedIn, Facebook
- **JWT tokens** with 24h expiry
- **Refresh tokens** with 7d expiry
- Token rotation on refresh
- Secure cookie storage for tokens

### Authorization

- Role-based access control (RBAC)
- Roles: `user`, `admin`
- Permission checks on all endpoints
- Resource ownership validation

### Rate Limiting

Rate limiting is enabled by default:

| Endpoint Type | Authenticated | Unauthenticated |
|--------------|---------------|-----------------|
| Submissions | 5/hour | 2/hour |
| Validation | 20/hour | 10/hour |
| General API | 100/minute | 20/minute |

Configuration:
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_SUBMISSIONS_PER_HOUR=5
RATE_LIMIT_VALIDATE_PER_HOUR=20
REDIS_URL=redis://localhost:6379  # For distributed state
```

### Input Validation

- All inputs validated via Pydantic schemas
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via output encoding
- Content moderation for user-submitted text

### Code Execution Security

User code runs in isolated containers with:
- Network access only to cluster peer nodes
- Resource limits:
  - CPU: 1 vCPU
  - Memory: 512Mi
  - Max execution time: 5 minutes
- Read-only filesystem (except /tmp)
- No access to cloud metadata service
- Separate service account per deployment

### Secrets Management

- Secrets stored in environment variables
- Support for GCP Secret Manager
- Never logged or exposed in errors
- Rotated regularly

```bash
# Required secrets
JWT_SECRET_KEY=your-secret-key
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_CLIENT_SECRET=xxx
GCP_CREDENTIALS_PATH=/path/to/service-account.json
```

### Data Protection

- Passwords never stored (OAuth only)
- User data export available via `/api/auth/download-data`
- Account deletion via `/api/auth/delete-account`
- GDPR compliance ready

## Security Headers

Applied to all responses:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000
```

## CORS Configuration

```python
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Incident Response

### Detection

- Real-time monitoring via Cloud Monitoring
- Alerts for:
  - High error rates
  - Failed authentication spikes
  - Unusual API patterns
  - Resource exhaustion

### Response Procedure

1. **Detect** via monitoring/alerts
2. **Assess** severity and scope
3. **Contain** the incident
4. **Investigate** root cause
5. **Remediate** and recover
6. **Document** and review

### Contact

For security issues, please report via GitHub Security Advisories or contact the maintainers directly.

## Compliance

### Data Retention

- Audit logs: 90 days
- Submission data: Until user deletion
- Deployment artifacts: 24 hours after cleanup

### User Rights

Users can:
- View their activity log
- Download their data
- Delete their account
- Request data correction

## Monitoring

### Health Checks

- `/health` - Basic health check
- `/` - Version and service info

### Metrics

Track via Cloud Monitoring:
- Request latency (p50, p95, p99)
- Error rates
- Authentication failures
- Rate limit hits

### Alerts

Configure alerts for:
- Error rate > 1%
- Latency p99 > 5s
- Failed auth > 10/minute
- Rate limit exhaustion

# Architecture Documentation

This document provides a detailed overview of the System Design Interview Platform architecture.

## System Overview

The platform is designed as a modern web application with a clear separation between frontend and backend, following microservices-ready patterns.

```
                                    ┌─────────────────┐
                                    │   User Browser  │
                                    └────────┬────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              Frontend                                   │
│                         React + TypeScript                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │    Router    │ │  AuthContext │ │   API Client │ │  Components  │  │
│  │ (react-router)│ │   (Context)  │ │   (axios)    │ │   (Monaco)   │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │ HTTP/REST
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                              Backend                                    │
│                         FastAPI + Python                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                         API Layer                                 │  │
│  │  ┌────────┐  ┌────────┐  ┌────────────┐  ┌────────────────────┐ │  │
│  │  │  Auth  │  │Problems│  │Submissions │  │       Tests        │ │  │
│  │  │  API   │  │  API   │  │    API     │  │        API         │ │  │
│  │  └────────┘  └────────┘  └────────────┘  └────────────────────┘ │  │
│  │  ┌────────┐  ┌────────┐  ┌────────────┐  ┌────────────────────┐ │  │
│  │  │ User   │  │ Assets │  │Distributed │  │       Chat/AI      │ │  │
│  │  │  API   │  │  API   │  │    API     │  │        API         │ │  │
│  │  └────────┘  └────────┘  └────────────┘  └────────────────────┘ │  │
│  │                      ┌────────────────────┐                      │  │
│  │                      │     Admin API      │                      │  │
│  │                      └────────────────────┘                      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                       Service Layer                               │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────────────┐ │  │
│  │  │ Orchestrator │──│  Validation   │──│    AI Service         │ │  │
│  │  │   Service    │  │   Service     │  │   (Claude API)        │ │  │
│  │  └──────┬───────┘  └───────────────┘  └───────────────────────┘ │  │
│  │         │                                                         │  │
│  │         ▼                                                         │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────────────┐ │  │
│  │  │  Terraform   │──│  GCP Service  │──│    Test Runner        │ │  │
│  │  │   Service    │  │               │  │ (Func/Perf/Chaos)     │ │  │
│  │  └──────────────┘  └───────────────┘  └───────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                        Data Layer                                 │  │
│  │  ┌────────────────┐  ┌─────────────────────────────────────────┐│  │
│  │  │  SQLAlchemy    │  │           Pydantic Schemas              ││  │
│  │  │    Models      │  │      (Request/Response Validation)      ││  │
│  │  └────────────────┘  └─────────────────────────────────────────┘│  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
         │                              │                      │
         ▼                              ▼                      ▼
   ┌──────────┐                  ┌──────────┐            ┌──────────┐
   │PostgreSQL│                  │  Redis   │            │   GCP    │
   │ Database │                  │  Cache   │            │ Platform │
   └──────────┘                  └──────────┘            └──────────┘
```

## Component Details

### Frontend Architecture

The frontend is a single-page application (SPA) built with React and TypeScript.

#### Key Components

1. **AuthContext** (`src/components/AuthContext.tsx`)
   - Manages authentication state globally
   - Handles token storage and refresh
   - Provides `useAuth()` hook for components

2. **API Client** (`src/api/client.ts`)
   - Centralized Axios instance with interceptors
   - Automatic token injection
   - Error handling and auth redirects

3. **Editors**
   - `SchemaEditor`: Monaco-based JSON editor for database schemas
   - `ApiSpecEditor`: Monaco-based JSON editor for API specifications
   - `DesignEditor`: Free-form text editor for design descriptions

4. **Pages**
   - `ProblemList`: Grid view of available problems
   - `ProblemDetail`: Full problem description with hints
   - `Submission`: Multi-step submission wizard
   - `Results`: Real-time results dashboard with polling

### Backend Architecture

The backend follows a layered architecture pattern.

#### Layer 1: API Routes (`backend/api/`)

Thin controllers that handle HTTP requests and delegate to services.

```python
@router.post("/submissions")
async def create_submission(
    submission_data: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate input
    # Create submission record
    # Trigger async processing
    background_tasks.add_task(orchestrator.process_submission, submission.id)
    return submission
```

#### Layer 2: Services (`backend/services/`)

Business logic and external integrations.

| Service | Responsibility |
|---------|---------------|
| `AIService` | Claude API integration for validation and generation |
| `ValidationService` | Rule-based + AI validation |
| `TerraformService` | Generate and execute Terraform |
| `GCPService` | GCP resource management |
| `TestRunner` | Execute functional, performance, chaos tests |
| `ChaosService` | Chaos experiment definitions |
| `Orchestrator` | Pipeline coordination |
| `DistributedBuildService` | Compile and deploy distributed consensus code to GCP |
| `DistributedTestService` | Run gRPC-based distributed tests (Raft, Paxos, 2PC, etc.) |
| `AuditService` | Track user actions and system events |
| `CleanupScheduler` | Automatic resource cleanup for expired deployments |
| `ErrorAnalyzer` | AI-powered analysis of build and test failures |
| `ModerationService` | Content moderation for user submissions |

#### Layer 3: Data (`backend/models/`, `backend/schemas/`)

- **Models**: SQLAlchemy ORM classes mapping to database tables
- **Schemas**: Pydantic models for request/response validation

### Database Schema

```
┌─────────────────┐       ┌─────────────────┐
│      users      │       │    problems     │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ google_id       │       │ title           │
│ email           │       │ description     │
│ name            │       │ difficulty      │
│ avatar_url      │       │ expected_schema │
│ created_at      │       │ expected_api_spec│
└────────┬────────┘       │ validation_rules│
         │                │ hints           │
         │                │ tags            │
         │                │ created_at      │
         │                └────────┬────────┘
         │                         │
         │    ┌────────────────────┘
         │    │
         ▼    ▼
┌─────────────────────────┐
│      submissions        │
├─────────────────────────┤
│ id (PK)                 │
│ problem_id (FK)         │───────┐
│ user_id (FK)            │       │
│ schema_input            │       │
│ api_spec_input          │       │
│ design_text             │       │
│ generated_terraform     │       │
│ deployment_id           │       │
│ namespace               │       │
│ status                  │       │
│ error_message           │       │
│ validation_feedback     │       │
│ created_at              │       │
│ updated_at              │       │
└─────────────────────────┘       │
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │     test_results        │
                    ├─────────────────────────┤
                    │ id (PK)                 │
                    │ submission_id (FK)      │
                    │ test_type               │
                    │ test_name               │
                    │ status                  │
                    │ details                 │
                    │ duration_ms             │
                    │ chaos_scenario          │
                    │ created_at              │
                    └─────────────────────────┘
```

### Submission Pipeline

The orchestrator manages the complete submission lifecycle:

```
                    ┌─────────────────────┐
                    │   Create Submission │
                    │     (API Call)      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Status: PENDING    │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    VALIDATION STAGE                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  1. Rule-based schema validation                       │  │
│  │  2. Rule-based API spec validation                     │  │
│  │  3. Claude AI design validation                        │  │
│  │     - Scalability assessment                           │  │
│  │     - Reliability assessment                           │  │
│  │     - Data model assessment                            │  │
│  │     - API design assessment                            │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
              VALID │                     │ INVALID
                    ▼                     ▼
         ┌─────────────────┐    ┌─────────────────────┐
         │Status: GENERATING│    │Status: VALIDATION   │
         │    _INFRA       │    │      _FAILED        │
         └────────┬────────┘    └─────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│                 TERRAFORM GENERATION                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  1. Send design to Claude with Terraform prompt        │  │
│  │  2. Extract Terraform code from response               │  │
│  │  3. Create workspace with generated code               │  │
│  │  4. Add provider configuration                         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Status: DEPLOYING  │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT STAGE                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  1. terraform init                                     │  │
│  │  2. terraform plan                                     │  │
│  │  3. terraform apply                                    │  │
│  │  4. Capture outputs (endpoints, resources)             │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
             SUCCESS│                     │ FAILURE
                    ▼                     ▼
         ┌─────────────────┐    ┌─────────────────────┐
         │ Status: TESTING │    │ Status: DEPLOY      │
         │                 │    │        _FAILED      │
         └────────┬────────┘    └─────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│                     TESTING STAGE                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  FUNCTIONAL TESTS (pytest)                             │  │
│  │  - API endpoint tests                                  │  │
│  │  - Error handling tests                                │  │
│  │  - Authentication tests                                │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PERFORMANCE TESTS (Locust)                            │  │
│  │  - Load testing                                        │  │
│  │  - Latency measurements                                │  │
│  │  - Throughput measurements                             │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  CHAOS TESTS (Chaos Toolkit)                           │  │
│  │  - Service failure recovery                            │  │
│  │  - Zone failure handling                               │  │
│  │  - Network partition resilience                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Status: COMPLETED  │
                    └─────────────────────┘
```

### Authentication Flow

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Browser │          │  Backend │          │  Google  │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                     │
     │  Click Login        │                     │
     │────────────────────>│                     │
     │                     │                     │
     │  Redirect to Google │                     │
     │<────────────────────│                     │
     │                     │                     │
     │  Auth Request       │                     │
     │─────────────────────────────────────────>│
     │                     │                     │
     │  Auth Code          │                     │
     │<─────────────────────────────────────────│
     │                     │                     │
     │  Callback with Code │                     │
     │────────────────────>│                     │
     │                     │                     │
     │                     │  Exchange Code      │
     │                     │────────────────────>│
     │                     │                     │
     │                     │  Access Token       │
     │                     │<────────────────────│
     │                     │                     │
     │                     │  Get User Info      │
     │                     │────────────────────>│
     │                     │                     │
     │                     │  User Details       │
     │                     │<────────────────────│
     │                     │                     │
     │  JWT Token          │                     │
     │<────────────────────│                     │
     │                     │                     │
```

### Security Considerations

1. **Authentication**
   - OAuth 2.0 with Google for secure authentication
   - JWT tokens with configurable expiration
   - HTTPBearer authentication for API endpoints

2. **Authorization**
   - Users can only access their own submissions
   - Admin endpoints protected (TODO: role-based access)

3. **Data Protection**
   - Sensitive data (API keys, tokens) stored in environment variables
   - GCP service account credentials never exposed
   - CORS configured for allowed origins only

4. **Infrastructure Isolation**
   - Each candidate's deployment uses unique namespace
   - Resources labeled for tracking and cleanup
   - Separate service accounts per deployment

### Scalability Considerations

1. **Frontend**
   - Static assets can be served via CDN
   - Code splitting for lazy loading

2. **Backend**
   - Stateless design allows horizontal scaling
   - Background tasks for long-running operations
   - Database connection pooling

3. **Testing**
   - Tests run asynchronously
   - Parallel test execution where possible

4. **Future Improvements**
   - Redis for session storage and caching
   - Message queue for task distribution
   - Kubernetes for container orchestration

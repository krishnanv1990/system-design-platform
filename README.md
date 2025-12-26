# System Design Interview Platform

A LeetCode-like platform for practicing system design interviews with AI-powered validation, real infrastructure deployment, and comprehensive testing including chaos engineering.

## Features

- **Problem Library**: Curated system design problems (URL Shortener, Rate Limiter, Distributed Cache, etc.)
- **Interactive Editors**: Monaco-based editors for database schema and API specification
- **AI Validation**: Claude-powered design review with detailed feedback and scoring
- **Infrastructure Deployment**: Automatic Terraform generation and GCP deployment
- **Comprehensive Testing**:
  - Functional API tests
  - Performance/load tests with Locust
  - Chaos engineering tests (service, zone, regional failures)
- **Detailed Results**: Real-time status updates and comprehensive test reports

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│                    React + TypeScript + Vite                     │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │
│   │  Login  │  │Problems │  │Submit   │  │ Results Dashboard│   │
│   │  OAuth  │  │  List   │  │Solution │  │   (Real-time)   │   │
│   └─────────┘  └─────────┘  └─────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend                                  │
│                    Python + FastAPI                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐    │
│   │  Auth API   │  │ Problems API│  │  Submissions API    │    │
│   │  (OAuth+JWT)│  │   (CRUD)    │  │  (Create + Status)  │    │
│   └─────────────┘  └─────────────┘  └─────────────────────┘    │
│                              │                                   │
│   ┌──────────────────────────┴──────────────────────────┐      │
│   │                  Orchestrator                         │      │
│   │  Validation → Terraform Gen → Deploy → Test → Report │      │
│   └──────────────────────────────────────────────────────┘      │
│                              │                                   │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │
│   │ Claude  │  │Terraform│  │  GCP    │  │   Test Runner   │   │
│   │   AI    │  │ Service │  │ Service │  │ (Func/Perf/Chaos)│   │
│   └─────────┘  └─────────┘  └─────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────────┐
        │PostgreSQL│   │  Redis   │   │     GCP      │
        │ Database │   │  Cache   │   │ (Deployment) │
        └──────────┘   └──────────┘   └──────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Monaco Editor |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| AI | Claude API (Anthropic) |
| Infrastructure | Terraform, Google Cloud Platform |
| Testing | Pytest, Locust, Chaos Toolkit |
| Auth | Google OAuth 2.0, JWT |
| Containerization | Docker, Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)
- Google Cloud account (for deployment features)
- Anthropic API key (for AI features)

### 1. Clone the Repository

```bash
git clone https://github.com/krishnanv1990/system-design-platform.git
cd system-design-platform
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required for AI features
ANTHROPIC_API_KEY=your-anthropic-api-key

# Required for authentication
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Required for GCP deployment
GCP_PROJECT_ID=your-gcp-project-id
GCP_CREDENTIALS_PATH=/path/to/service-account.json
```

### 3. Start the Application

```bash
docker-compose up -d
```

### 4. Seed Sample Problems

```bash
# Using Docker
docker-compose exec backend python backend/seed_data.py

# Or locally
python backend/seed_data.py
```

### 5. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Development Setup

### Backend Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis
docker-compose up -d db redis

# Run backend
uvicorn backend.main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
system-design-platform/
├── backend/
│   ├── api/                 # API route handlers
│   │   ├── auth.py         # Authentication endpoints
│   │   ├── problems.py     # Problem CRUD
│   │   ├── submissions.py  # Submission handling
│   │   └── tests.py        # Test results
│   ├── auth/               # Authentication logic
│   │   ├── jwt_handler.py  # JWT token management
│   │   └── oauth.py        # Google OAuth integration
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic validation schemas
│   ├── services/           # Business logic
│   │   ├── ai_service.py   # Claude AI integration
│   │   ├── chaos_service.py # Chaos engineering
│   │   ├── gcp_service.py  # GCP resource management
│   │   ├── orchestrator.py # Pipeline coordination
│   │   ├── terraform_service.py # IaC generation
│   │   ├── test_runner.py  # Test execution
│   │   └── validation_service.py # Design validation
│   ├── prompts/            # AI prompt templates
│   ├── config.py           # Configuration management
│   ├── database.py         # Database connection
│   ├── main.py             # FastAPI application
│   └── seed_data.py        # Sample data seeder
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   └── types/          # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── terraform_templates/    # Terraform module templates
├── tests/                  # Test specifications
│   ├── functional/
│   ├── performance/
│   └── chaos/
├── docker-compose.yml
├── Dockerfile.backend
└── requirements.txt
```

## API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/google` | GET | Initiate Google OAuth flow |
| `/api/auth/google/callback` | GET | OAuth callback handler |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/logout` | POST | Logout user |

### Problems

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/problems` | GET | List all problems |
| `/api/problems/{id}` | GET | Get problem details |
| `/api/problems` | POST | Create problem (admin) |
| `/api/problems/{id}` | PUT | Update problem (admin) |
| `/api/problems/{id}` | DELETE | Delete problem (admin) |

### Submissions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/submissions` | POST | Submit a solution |
| `/api/submissions` | GET | List user's submissions |
| `/api/submissions/{id}` | GET | Get submission details |
| `/api/submissions/validate` | POST | Validate without submitting |

### Tests

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tests/submission/{id}` | GET | Get submission test results |
| `/api/tests/submission/{id}/summary` | GET | Get test summary |
| `/api/tests/{id}` | GET | Get specific test result |

## Submission Pipeline

When a user submits a solution, it goes through the following stages:

1. **Pending** → Submission received
2. **Validating** → AI validates the design
3. **Generating Infrastructure** → Terraform code generated
4. **Deploying** → Infrastructure deployed to GCP
5. **Testing** → Running functional, performance, and chaos tests
6. **Completed** → All tests finished

```
Submit → Validate → Generate Terraform → Deploy → Test → Report
           │              │                │        │
           ▼              ▼                ▼        ▼
        Claude AI    AI + Templates    Terraform  Pytest
        Feedback     Generation        Apply      Locust
                                                  Chaos Toolkit
```

## Chaos Engineering Scenarios

The platform tests solutions against various failure scenarios:

| Scenario | Description | Expected Behavior |
|----------|-------------|-------------------|
| Service Failure | Single instance goes down | Auto-recovery |
| Zone Failure | Entire availability zone fails | Cross-zone failover |
| Regional Failure | Entire region unavailable | Multi-region failover |
| Network Partition | Network split between services | Graceful degradation |
| Latency Injection | Artificial delays added | Timeout handling |
| Database Failure | Database becomes unavailable | Queue or cache fallback |
| Cache Failure | Cache layer fails | Database fallback |

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Yes |
| `JWT_SECRET_KEY` | Secret for JWT signing | Yes |
| `ANTHROPIC_API_KEY` | Claude API key | For AI features |
| `GCP_PROJECT_ID` | Google Cloud project | For deployment |
| `GCP_REGION` | GCP region | For deployment |
| `GCP_CREDENTIALS_PATH` | Service account key path | For deployment |

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `http://localhost:8000/api/auth/google/callback`
4. Copy Client ID and Secret to `.env`

### GCP Setup

1. Create a GCP project
2. Enable required APIs (Compute, Cloud Run, Cloud SQL, etc.)
3. Create a service account with appropriate permissions
4. Download the JSON key file
5. Set `GCP_CREDENTIALS_PATH` in `.env`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Anthropic Claude](https://www.anthropic.com/) for AI capabilities
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent Python framework
- [Chaos Toolkit](https://chaostoolkit.org/) for chaos engineering
- [Locust](https://locust.io/) for load testing

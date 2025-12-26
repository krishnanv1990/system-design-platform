# Development Guide

This guide covers development practices, code structure, and how to extend the platform.

## Table of Contents

- [Project Structure](#project-structure)
- [Development Environment](#development-environment)
- [Backend Development](#backend-development)
- [Frontend Development](#frontend-development)
- [Testing](#testing)
- [Adding New Features](#adding-new-features)
- [Code Style](#code-style)

## Project Structure

```
system-design-platform/
├── backend/                    # Python FastAPI backend
│   ├── api/                   # API route handlers
│   │   ├── __init__.py       # Router aggregation
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── problems.py       # Problem CRUD endpoints
│   │   ├── submissions.py    # Submission endpoints
│   │   └── tests.py          # Test result endpoints
│   ├── auth/                  # Authentication logic
│   │   ├── jwt_handler.py    # JWT creation/verification
│   │   └── oauth.py          # Google OAuth integration
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py          # User model
│   │   ├── problem.py       # Problem model
│   │   ├── submission.py    # Submission model
│   │   └── test_result.py   # Test result model
│   ├── schemas/              # Pydantic validation schemas
│   │   ├── user.py          # User request/response schemas
│   │   ├── problem.py       # Problem schemas
│   │   ├── submission.py    # Submission schemas
│   │   └── test_result.py   # Test result schemas
│   ├── services/             # Business logic services
│   │   ├── ai_service.py    # Claude API integration
│   │   ├── validation_service.py
│   │   ├── terraform_service.py
│   │   ├── gcp_service.py
│   │   ├── test_runner.py
│   │   ├── chaos_service.py
│   │   └── orchestrator.py  # Pipeline coordination
│   ├── prompts/              # AI prompt templates
│   ├── config.py             # Configuration management
│   ├── database.py           # Database connection
│   ├── main.py               # FastAPI application
│   └── seed_data.py          # Sample data seeder
├── frontend/                  # React TypeScript frontend
│   ├── src/
│   │   ├── api/             # API client
│   │   ├── components/      # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── types/           # TypeScript types
│   │   ├── App.tsx          # Main app component
│   │   └── main.tsx         # Entry point
│   ├── package.json
│   └── vite.config.ts
├── docs/                      # Documentation
├── terraform_templates/       # Terraform module templates
├── tests/                     # Test specifications
├── docker-compose.yml
├── Dockerfile.backend
└── requirements.txt
```

## Development Environment

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose
- Git

### Initial Setup

```bash
# Clone repository
git clone https://github.com/krishnanv1990/system-design-platform.git
cd system-design-platform

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Start dependencies
docker-compose up -d db redis
```

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio ruff black mypy

# Start backend with hot reload
uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Running with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend frontend

# Rebuild after changes
docker-compose up -d --build
```

## Backend Development

### Adding a New API Endpoint

1. **Create the route handler** in `backend/api/`:

```python
# backend/api/new_feature.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.auth.jwt_handler import get_current_user

router = APIRouter()

@router.get("/new-endpoint")
async def get_new_thing(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Endpoint description."""
    return {"message": "Hello"}
```

2. **Register the router** in `backend/api/__init__.py`:

```python
from backend.api.new_feature import router as new_feature_router

api_router.include_router(
    new_feature_router,
    prefix="/new-feature",
    tags=["New Feature"]
)
```

### Adding a New Model

1. **Create the model** in `backend/models/`:

```python
# backend/models/new_model.py
from sqlalchemy import Column, Integer, String, DateTime
from backend.database import Base
from datetime import datetime

class NewModel(Base):
    __tablename__ = "new_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

2. **Add to `backend/models/__init__.py`**:

```python
from backend.models.new_model import NewModel
```

3. **Create corresponding schema** in `backend/schemas/`:

```python
# backend/schemas/new_model.py
from pydantic import BaseModel
from datetime import datetime

class NewModelCreate(BaseModel):
    name: str

class NewModelResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
```

### Adding a New Service

```python
# backend/services/new_service.py
from typing import Optional

class NewService:
    """Service for handling new feature logic."""

    def __init__(self):
        # Initialize dependencies
        pass

    async def do_something(self, input: str) -> dict:
        """Process input and return result."""
        # Business logic here
        return {"result": input.upper()}
```

### Working with the AI Service

```python
from backend.services.ai_service import AIService

ai_service = AIService()

# Validate a design
result = await ai_service.validate_design(
    problem_description="Design a URL shortener",
    design_text="My design includes...",
    schema_input={"tables": {}},
    api_spec_input={"endpoints": []}
)

# Generate Terraform
terraform_code = await ai_service.generate_terraform(
    problem_description="Design a URL shortener",
    design_text="My design includes...",
    namespace="candidate-1"
)

# Generate tests
test_specs = await ai_service.generate_tests(
    problem_description="Design a URL shortener",
    design_text="My design includes...",
    endpoint_url="https://example.com"
)
```

## Frontend Development

### Component Structure

Components follow this pattern:

```tsx
// frontend/src/components/MyComponent.tsx

interface MyComponentProps {
  title: string;
  onAction: () => void;
}

export default function MyComponent({ title, onAction }: MyComponentProps) {
  return (
    <div className="p-4 bg-white rounded-lg shadow">
      <h2 className="text-lg font-medium">{title}</h2>
      <button
        onClick={onAction}
        className="mt-2 px-4 py-2 bg-primary-600 text-white rounded"
      >
        Click Me
      </button>
    </div>
  );
}
```

### Adding a New Page

1. **Create the page component** in `frontend/src/pages/`:

```tsx
// frontend/src/pages/NewPage.tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';

export default function NewPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch data
    setLoading(false);
  }, [id]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>New Page</h1>
    </div>
  );
}
```

2. **Add route** in `frontend/src/App.tsx`:

```tsx
import NewPage from './pages/NewPage';

// In Routes
<Route path="new-feature/:id" element={<NewPage />} />
```

### Using the API Client

```tsx
import { problemsApi, submissionsApi } from '../api/client';

// List problems
const problems = await problemsApi.list({ difficulty: 'medium' });

// Get problem
const problem = await problemsApi.get(1);

// Create submission
const submission = await submissionsApi.create({
  problem_id: 1,
  schema_input: {},
  api_spec_input: {},
  design_text: "My design..."
});

// Validate
const validation = await submissionsApi.validate({
  problem_id: 1,
  design_text: "My design..."
});
```

### Styling with Tailwind

The project uses Tailwind CSS. Common patterns:

```tsx
// Buttons
<button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
  Primary Button
</button>

// Cards
<div className="bg-white rounded-lg shadow border p-6">
  Card content
</div>

// Status badges
<span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
  Passed
</span>

// Form inputs
<input
  type="text"
  className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
/>
```

## Testing

### Backend Tests

```bash
# Run all tests
pytest backend/ -v

# Run specific test file
pytest backend/tests/test_api.py -v

# Run with coverage
pytest backend/ --cov=backend --cov-report=html
```

Example test:

```python
# backend/tests/test_problems.py
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_list_problems():
    response = client.get("/api/problems")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm run test

# Run with coverage
npm run test -- --coverage
```

### Integration Tests

```bash
# Start services
docker-compose up -d

# Run integration tests
pytest tests/integration/ -v
```

## Adding New Features

### Example: Adding a Leaderboard

1. **Backend Model**:

```python
# backend/models/leaderboard.py
class LeaderboardEntry(Base):
    __tablename__ = "leaderboard"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    problem_id = Column(Integer, ForeignKey("problems.id"))
    score = Column(Integer)
    rank = Column(Integer)
```

2. **Backend Schema**:

```python
# backend/schemas/leaderboard.py
class LeaderboardEntryResponse(BaseModel):
    rank: int
    user_name: str
    score: int
    problem_title: str
```

3. **Backend Service**:

```python
# backend/services/leaderboard_service.py
class LeaderboardService:
    def get_leaderboard(self, problem_id: int, limit: int = 10):
        # Query and return top scores
        pass
```

4. **Backend API**:

```python
# backend/api/leaderboard.py
@router.get("/problems/{problem_id}/leaderboard")
async def get_leaderboard(problem_id: int):
    service = LeaderboardService()
    return service.get_leaderboard(problem_id)
```

5. **Frontend API Client**:

```typescript
// frontend/src/api/client.ts
export const leaderboardApi = {
  get: async (problemId: number) => {
    const response = await api.get(`/leaderboard/problems/${problemId}`)
    return response.data
  }
}
```

6. **Frontend Component**:

```tsx
// frontend/src/components/Leaderboard.tsx
export default function Leaderboard({ problemId }: { problemId: number }) {
  const [entries, setEntries] = useState([]);

  useEffect(() => {
    leaderboardApi.get(problemId).then(setEntries);
  }, [problemId]);

  return (
    <div>
      {entries.map(entry => (
        <div key={entry.rank}>
          #{entry.rank} - {entry.user_name}: {entry.score}
        </div>
      ))}
    </div>
  );
}
```

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Use docstrings for public functions

```bash
# Format code
black backend/

# Lint
ruff check backend/

# Type check
mypy backend/
```

### TypeScript

- Use functional components
- Use TypeScript strictly (no `any`)
- Use named exports

```bash
cd frontend

# Lint
npm run lint

# Type check
npx tsc --noEmit
```

### Git Commits

Follow conventional commits:

```
feat: add leaderboard feature
fix: correct validation error handling
docs: update API documentation
refactor: simplify test runner
test: add submission tests
```

### Pull Request Process

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and commit
3. Push and create PR
4. Ensure CI passes
5. Request review
6. Merge after approval

# Contributing to System Design Platform

Thank you for your interest in contributing!

## Development Setup

1. Clone the repository
   ```bash
   git clone https://github.com/krishnanv1990/system-design-platform.git
   cd system-design-platform
   ```

2. Install dependencies:
   ```bash
   # Backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   # Frontend
   cd frontend && npm install
   ```

3. Set up environment variables
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. Start development servers:
   ```bash
   # Database (required)
   docker-compose up -d db redis

   # Backend
   uvicorn backend.main:app --reload --port 8000

   # Frontend (in another terminal)
   cd frontend && npm run dev
   ```

## Code Style

### Python

- Follow PEP 8
- Use type hints for all functions
- Run `black` and `isort` before committing
- Maximum line length: 88 characters

```bash
# Format code
black backend/
isort backend/

# Check types
mypy backend/
```

### TypeScript

- Use strict mode
- Avoid `any` type - define proper interfaces
- Run `eslint` and `prettier` before committing

```bash
cd frontend
npm run lint
npm run format
```

## Testing

- Write tests for new features
- Maintain test coverage above 80%
- Run tests before submitting PR:

```bash
# Backend tests
pytest backend/tests/ -v

# Frontend tests
cd frontend && npm test

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

## Pull Request Process

1. Create a feature branch from `main`
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes with clear commits

3. Update documentation if needed

4. Add tests for new functionality

5. Ensure all tests pass
   ```bash
   pytest backend/tests/
   cd frontend && npm test
   ```

6. Push and submit PR with clear description

## Commit Messages

Follow conventional commits:

| Prefix | Description |
|--------|-------------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `refactor:` | Code refactoring |
| `test:` | Test additions/changes |
| `chore:` | Maintenance tasks |
| `perf:` | Performance improvements |

Examples:
```
feat: add WebSocket support for real-time updates
fix: correct rate limit calculation for authenticated users
docs: update API documentation with new endpoints
refactor: extract common validation logic to utils
```

## Adding New Problems

### System Design Problems

1. Add problem definition to `backend/seed_data.py`
2. Add validation rules if needed
3. Add test cases in `tests/functional/`
4. Update documentation

### Distributed Consensus Problems

1. Create problem entry with:
   - Title and description
   - Proto definition
   - Starter code templates (Python, Go, Rust, Java)
   - Test cases

2. Add test scenarios in `backend/services/distributed_tests_{name}.py`

3. Update problem registry

## Directory Structure

```
system-design-platform/
├── backend/
│   ├── api/           # API routes
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── middleware/    # Middleware (auth, rate limiting)
│   └── tests/         # Unit tests
├── frontend/
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   ├── api/         # API client
│   │   └── hooks/       # Custom hooks
│   └── tests/           # Frontend tests
├── tests/               # Integration/E2E tests
└── docs/                # Documentation
```

## Code Review Guidelines

When reviewing PRs:

- Check for proper error handling
- Verify tests are included
- Ensure documentation is updated
- Look for security issues
- Verify type safety

## Security Considerations

- Never commit secrets or credentials
- Use environment variables for configuration
- Sanitize all user inputs
- Follow OWASP guidelines

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Use discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the project's license.

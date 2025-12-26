"""
Claude AI service for design validation and code generation.
Provides integration with Anthropic's Claude API.
"""

import json
from typing import Optional, Dict, Any
import anthropic

from backend.config import get_settings
from backend.prompts.validate_design import DESIGN_VALIDATION_PROMPT
from backend.prompts.generate_terraform import TERRAFORM_GENERATION_PROMPT
from backend.prompts.generate_tests import TEST_GENERATION_PROMPT

settings = get_settings()


class AIService:
    """
    Service for interacting with Claude AI.
    Handles design validation, Terraform generation, and test generation.
    """

    def __init__(self):
        """Initialize the Anthropic client."""
        # Only use mock AI responses if no valid API key is provided
        # (DEMO_MODE setting only affects authentication, not AI)
        has_valid_api_key = settings.anthropic_api_key and settings.anthropic_api_key != "demo-key"
        self.demo_mode = not has_valid_api_key
        if has_valid_api_key:
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        else:
            self.client = None
        self.model = "claude-sonnet-4-20250514"

    async def validate_design(
        self,
        problem_description: str,
        design_text: str,
        schema_input: Optional[Dict[str, Any]] = None,
        api_spec_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate a system design using Claude.

        Args:
            problem_description: The problem being solved
            design_text: Candidate's design description
            schema_input: Database schema design
            api_spec_input: API specification

        Returns:
            Validation result with feedback
        """
        # Return mock response in demo mode
        if self.demo_mode:
            return {
                "is_valid": True,
                "feedback": "Demo Mode: Your design has been accepted for demonstration purposes. In production, Claude AI would provide detailed feedback on your system design including architecture review, scalability analysis, and specific recommendations.",
                "errors": [],
                "warnings": ["Demo mode is enabled - AI validation is simulated"],
                "suggestions": [
                    "Consider adding caching layer for improved read performance",
                    "Think about data partitioning strategy for horizontal scaling",
                    "Include monitoring and observability in your design"
                ],
                "score": 85,
            }

        # Build the context for Claude
        context = f"""
Problem Description:
{problem_description}

Candidate's Design:
{design_text}
"""
        if schema_input:
            context += f"\nDatabase Schema:\n{json.dumps(schema_input, indent=2)}"

        if api_spec_input:
            context += f"\nAPI Specification:\n{json.dumps(api_spec_input, indent=2)}"

        # Call Claude for validation
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=DESIGN_VALIDATION_PROMPT,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        # Parse the response
        response_text = message.content[0].text

        try:
            # Try to parse as JSON (Claude should return structured response)
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # If not JSON, wrap in a simple structure
            result = {
                "is_valid": True,
                "feedback": response_text,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "score": None,
            }

        return result

    async def generate_terraform(
        self,
        problem_description: str,
        design_text: str,
        schema_input: Optional[Dict[str, Any]] = None,
        api_spec_input: Optional[Dict[str, Any]] = None,
        namespace: str = "default",
    ) -> str:
        """
        Generate Terraform code from a system design.

        Args:
            problem_description: The problem being solved
            design_text: Candidate's design description
            schema_input: Database schema design
            api_spec_input: API specification
            namespace: Deployment namespace for isolation

        Returns:
            Generated Terraform code
        """
        # Return mock Terraform in demo mode
        if self.demo_mode:
            return f'''# Demo Mode - Terraform Generation Simulated
# In production, Claude AI would generate actual Terraform code

terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
}}

provider "google" {{
  project = "{settings.gcp_project_id or 'demo-project'}"
  region  = "{settings.gcp_region or 'us-central1'}"
}}

# Demo placeholder for {namespace}
resource "google_cloud_run_service" "{namespace}_api" {{
  name     = "{namespace}-api"
  location = "{settings.gcp_region or 'us-central1'}"

  template {{
    spec {{
      containers {{
        image = "gcr.io/demo/placeholder:latest"
      }}
    }}
  }}
}}
'''

        context = f"""
Problem: {problem_description}

Design Description:
{design_text}

Namespace/Prefix: {namespace}
Cloud Provider: Google Cloud Platform (GCP)
Region: {settings.gcp_region}
Project ID: {settings.gcp_project_id}
"""
        if schema_input:
            context += f"\nDatabase Schema:\n{json.dumps(schema_input, indent=2)}"

        if api_spec_input:
            context += f"\nAPI Specification:\n{json.dumps(api_spec_input, indent=2)}"

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=TERRAFORM_GENERATION_PROMPT,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        return message.content[0].text

    async def generate_tests(
        self,
        problem_description: str,
        design_text: str,
        api_spec_input: Optional[Dict[str, Any]] = None,
        endpoint_url: str = "",
    ) -> Dict[str, Any]:
        """
        Generate test specifications from a system design.

        Args:
            problem_description: The problem being solved
            design_text: Candidate's design description
            api_spec_input: API specification
            endpoint_url: Deployed endpoint URL

        Returns:
            Test specifications for functional, performance, and chaos tests
        """
        # Return mock tests in demo mode
        if self.demo_mode:
            return {
                "functional_tests": [
                    {"name": "test_health_endpoint", "description": "Verify health check returns 200", "passed": True},
                    {"name": "test_create_resource", "description": "Test resource creation", "passed": True},
                    {"name": "test_get_resource", "description": "Test resource retrieval", "passed": True},
                ],
                "performance_tests": [
                    {"name": "load_test", "description": "100 concurrent users", "rps": 500, "p99_latency_ms": 45},
                ],
                "chaos_tests": [
                    {"name": "network_partition", "description": "Simulate network failure", "recovered": True},
                ],
                "demo_mode": True,
            }

        context = f"""
Problem: {problem_description}

Design Description:
{design_text}

Deployed Endpoint: {endpoint_url}
"""
        if api_spec_input:
            context += f"\nAPI Specification:\n{json.dumps(api_spec_input, indent=2)}"

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=TEST_GENERATION_PROMPT,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        response_text = message.content[0].text

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            result = {
                "functional_tests": [],
                "performance_tests": [],
                "chaos_tests": [],
                "raw_response": response_text,
            }

        return result

    async def generate_api_code(
        self,
        problem_description: str,
        design_text: str,
        api_spec: Optional[Dict[str, Any]] = None,
        required_services: Optional[list] = None,
    ) -> str:
        """
        Generate FastAPI code from a candidate's design.

        Args:
            problem_description: The problem being solved
            design_text: Candidate's design description
            api_spec: API specification
            required_services: List of required infrastructure services

        Returns:
            Generated Python FastAPI code
        """
        # Return mock API code in demo mode
        if self.demo_mode:
            return '''"""
Demo Mode URL Shortener API
Auto-generated implementation for testing purposes.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, Any
from datetime import datetime
import hashlib
import random
import string

app = FastAPI(title="URL Shortener API", version="1.0.0")

# In-memory storage
urls_db: Dict[str, Dict[str, Any]] = {}
stats_db: Dict[str, int] = {}

# Pydantic models
class HealthResponse(BaseModel):
    status: str

class URLCreate(BaseModel):
    original_url: str = Field(..., min_length=1, max_length=2048)
    custom_code: Optional[str] = Field(None, min_length=3, max_length=20)
    expires_in_hours: Optional[int] = Field(None, ge=1, le=8760)

    @validator("original_url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class URLResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: str

class URLInfo(BaseModel):
    short_code: str
    original_url: str
    created_at: str
    click_count: int

# Helper functions
def generate_short_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))

# Health endpoints (REQUIRED)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"service": "URL Shortener API", "status": "running", "version": "1.0.0"}

# URL Shortener API endpoints
@app.post("/api/v1/urls", response_model=URLResponse, status_code=201)
async def create_short_url(data: URLCreate):
    try:
        # Generate or use custom short code
        if data.custom_code:
            if data.custom_code in urls_db:
                raise HTTPException(status_code=409, detail="Custom code already exists")
            short_code = data.custom_code
        else:
            short_code = generate_short_code()
            while short_code in urls_db:
                short_code = generate_short_code()

        # Store URL data
        urls_db[short_code] = {
            "original_url": data.original_url,
            "created_at": datetime.utcnow().isoformat(),
            "expires_in_hours": data.expires_in_hours,
        }
        stats_db[short_code] = 0

        return URLResponse(
            short_code=short_code,
            short_url=f"/{short_code}",
            original_url=data.original_url,
            created_at=urls_db[short_code]["created_at"],
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/v1/urls/{short_code}", response_model=URLInfo)
async def get_url_info(short_code: str):
    try:
        if short_code not in urls_db:
            raise HTTPException(status_code=404, detail="Short URL not found")

        url_data = urls_db[short_code]
        return URLInfo(
            short_code=short_code,
            original_url=url_data["original_url"],
            created_at=url_data["created_at"],
            click_count=stats_db.get(short_code, 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/v1/urls/{short_code}/stats")
async def get_url_stats(short_code: str):
    try:
        if short_code not in urls_db:
            raise HTTPException(status_code=404, detail="Short URL not found")

        return {
            "short_code": short_code,
            "click_count": stats_db.get(short_code, 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/v1/urls/{short_code}", status_code=204)
async def delete_url(short_code: str):
    try:
        if short_code not in urls_db:
            raise HTTPException(status_code=404, detail="Short URL not found")

        del urls_db[short_code]
        stats_db.pop(short_code, None)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/{short_code}")
async def redirect_to_url(short_code: str):
    try:
        if short_code not in urls_db:
            raise HTTPException(status_code=404, detail="Short URL not found")

        # Increment click count
        stats_db[short_code] = stats_db.get(short_code, 0) + 1

        # Redirect to original URL
        return RedirectResponse(url=urls_db[short_code]["original_url"], status_code=307)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
'''

        services_str = ", ".join(required_services or ["postgres"])

        context = f"""
Problem: {problem_description}

Candidate's Design:
{design_text}

Required Infrastructure Services: {services_str}
"""
        if api_spec:
            context += f"\nAPI Specification:\n{json.dumps(api_spec, indent=2)}"

        system_prompt = """You are an expert Python developer generating production-ready FastAPI code.

Generate a complete, working FastAPI application based on the candidate's system design.

CRITICAL Requirements - YOUR CODE MUST FOLLOW ALL OF THESE:

1. IMPORTS - Only use these standard/allowed imports:
   ```
   from fastapi import FastAPI, HTTPException, Query, Path, Body, Depends
   from fastapi.responses import JSONResponse, RedirectResponse
   from pydantic import BaseModel, Field, validator
   from typing import Optional, List, Dict, Any
   from datetime import datetime
   import hashlib
   import uuid
   import random
   import string
   import re
   ```
   DO NOT import: asyncpg, databases, sqlalchemy, redis, aioredis, motor, pymongo, psycopg2, mysql, kafka, elasticsearch, or ANY database/external service libraries

2. STORAGE - Use in-memory Python dictionaries ONLY:
   ```python
   # Global in-memory storage
   data_store: Dict[str, Any] = {}
   ```
   NO database connections, NO external services, NO environment variable lookups for connections

3. REQUIRED ENDPOINTS - You MUST include these EXACTLY:
   ```python
   @app.get("/health")
   async def health_check():
       return {"status": "healthy"}

   @app.get("/")
   async def root():
       return {"service": "API", "status": "running"}
   ```

4. ERROR HANDLING - Wrap all endpoint logic in try/except:
   ```python
   @app.post("/api/v1/resource")
   async def create_resource(data: ResourceCreate):
       try:
           # Implementation
           return result
       except ValueError as e:
           raise HTTPException(status_code=400, detail=str(e))
       except KeyError as e:
           raise HTTPException(status_code=404, detail=f"Not found: {e}")
       except Exception as e:
           raise HTTPException(status_code=500, detail="Internal server error")
   ```

5. INPUT VALIDATION - Use Pydantic models with validators:
   ```python
   class CreateRequest(BaseModel):
       url: str = Field(..., min_length=1, max_length=2048)

       @validator('url')
       def validate_url(cls, v):
           if not v.startswith(('http://', 'https://')):
               raise ValueError('URL must start with http:// or https://')
           return v
   ```

6. CODE STRUCTURE - Follow this exact structure:
   ```python
   from fastapi import FastAPI, HTTPException
   from pydantic import BaseModel, Field
   from typing import Dict, Optional
   # ... other safe imports

   app = FastAPI(title="Service Name")

   # In-memory storage
   storage: Dict[str, Any] = {}

   # Pydantic models
   class ItemCreate(BaseModel):
       ...

   # Health endpoints (REQUIRED)
   @app.get("/health")
   async def health():
       return {"status": "healthy"}

   @app.get("/")
   async def root():
       return {"status": "running"}

   # API endpoints
   @app.post("/api/v1/items")
   async def create_item(...):
       try:
           ...
       except Exception as e:
           raise HTTPException(status_code=500, detail=str(e))
   ```

7. NO STARTUP LOGIC - Do not include:
   - @app.on_event("startup") that connects to services
   - Global code that makes network calls
   - Code that reads files or environment variables for connections

8. DEFENSIVE CODING:
   - Check if keys exist before accessing: `storage.get(key)` not `storage[key]`
   - Validate input lengths and formats
   - Return proper HTTP status codes (200, 201, 400, 404, 500)
   - Never expose internal errors to clients

Return ONLY the Python code. No markdown, no explanations, no code blocks with ```.
The code must be syntactically valid and immediately runnable."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=system_prompt,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        code = message.content[0].text

        # Clean up any markdown code blocks if present
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

"""
Claude AI service for design validation and code generation.
Provides integration with Anthropic's Claude API.
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple
import anthropic

from backend.config import get_settings
from backend.prompts.validate_design import DESIGN_VALIDATION_PROMPT
from backend.prompts.generate_terraform import TERRAFORM_GENERATION_PROMPT
from backend.prompts.generate_tests import TEST_GENERATION_PROMPT

settings = get_settings()
logger = logging.getLogger(__name__)


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

        # Track token usage from last API call
        self._last_input_tokens = 0
        self._last_output_tokens = 0

    def get_last_usage(self) -> Tuple[int, int]:
        """
        Get token usage from the last API call.

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        return (self._last_input_tokens, self._last_output_tokens)

    def _track_usage(self, message) -> None:
        """
        Track token usage from an API response.

        Args:
            message: Anthropic API response message
        """
        if hasattr(message, 'usage'):
            self._last_input_tokens = getattr(message.usage, 'input_tokens', 0)
            self._last_output_tokens = getattr(message.usage, 'output_tokens', 0)
            logger.info(
                f"AI usage: input={self._last_input_tokens}, output={self._last_output_tokens}"
            )
        else:
            self._last_input_tokens = 0
            self._last_output_tokens = 0

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

        # Track token usage
        self._track_usage(message)

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

        # Track token usage
        self._track_usage(message)

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

        # Track token usage
        self._track_usage(message)

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

        # Track token usage
        self._track_usage(message)

        code = message.content[0].text

        # Clean up any markdown code blocks if present
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

    async def generate_design_summary(
        self,
        problem_description: str,
        problem_title: str,
        difficulty_level: str,
        level_requirements: str,
        conversation_history: list[Dict[str, str]],
        current_schema: Optional[Dict[str, Any]] = None,
        current_api_spec: Optional[Dict[str, Any]] = None,
        current_diagram: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive design summary after the chat session.

        Args:
            problem_description: The problem being solved
            problem_title: Title of the problem
            difficulty_level: Difficulty level (easy/medium/hard)
            level_requirements: Requirements for this difficulty level
            conversation_history: Previous messages in the conversation
            current_schema: Current database schema design (if any)
            current_api_spec: Current API specification (if any)
            current_diagram: Current diagram data (if any)

        Returns:
            Dict with summary, key_components, strengths, areas_for_improvement, overall_score
        """
        # Demo mode response
        if self.demo_mode:
            return {
                "summary": f"""## Design Summary for {problem_title}

This is a demo summary for your **{difficulty_level.upper()}** level ({self._get_level_label(difficulty_level)}) design.

### Your Design Approach
Based on the conversation, you have been working on designing a system that addresses the core requirements of the problem. Your design shows an understanding of the key concepts involved.

### Key Architecture Decisions
- You discussed the importance of using a Key Generation Service (KGS) for generating short codes
- Database design considerations were explored
- API endpoint structure was outlined

### Implementation Notes
In a production implementation, you would need to consider:
- Proper indexing strategies for your database
- Caching layers for improved read performance
- Monitoring and observability for production systems

*Demo mode: In production, Claude would provide a detailed analysis of your specific design decisions and conversation.*""",
                "key_components": [
                    "Key Generation Service (KGS)",
                    "Database for URL storage",
                    "API layer for CRUD operations",
                    "Caching layer (Redis)",
                    "Redirect service",
                ],
                "strengths": [
                    "Understanding of KGS for unique code generation",
                    "Consideration of database schema design",
                    "API endpoint structure planning",
                ],
                "areas_for_improvement": [
                    "Consider adding more details on caching strategy",
                    "Expand on error handling approaches",
                    "Discuss monitoring and observability",
                ],
                "overall_score": 75,
                "demo_mode": True,
            }

        # Build context for summary generation
        context = f"""
Problem: {problem_title}
Description: {problem_description}

Difficulty Level: {difficulty_level.upper()}
Level Requirements:
{level_requirements}

"""
        if current_schema:
            context += f"Candidate's Database Schema:\n{json.dumps(current_schema, indent=2)}\n\n"

        if current_api_spec:
            context += f"Candidate's API Specification:\n{json.dumps(current_api_spec, indent=2)}\n\n"

        if current_diagram:
            context += f"Candidate's Diagram Data:\n{json.dumps(current_diagram, indent=2)}\n\n"

        # Add conversation history summary
        if conversation_history:
            context += "Conversation History:\n"
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = "Candidate" if msg.get("role") == "user" else "Coach"
                context += f"{role}: {msg.get('content', '')[:500]}...\n"

        system_prompt = """You are generating a final design summary for a system design interview session.

Based on the conversation and artifacts provided, generate a comprehensive summary of the candidate's design.

Respond with JSON in this exact format:
{
    "summary": "A 2-3 paragraph markdown summary of the candidate's design approach, key decisions, and overall assessment",
    "key_components": ["List", "of", "key", "components", "in", "their", "design"],
    "strengths": ["List", "of", "strong", "points", "in", "their", "design"],
    "areas_for_improvement": ["List", "of", "areas", "that", "could", "be", "improved"],
    "overall_score": 0-100 based on how well the design meets the level requirements
}

Evaluate the design against the specific requirements for the difficulty level.
Be specific and constructive in your feedback."""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": context}]
        )

        # Track token usage
        self._track_usage(message)

        response_text = message.content[0].text

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            result = {
                "summary": response_text,
                "key_components": [],
                "strengths": [],
                "areas_for_improvement": [],
                "overall_score": None,
            }

        result["demo_mode"] = False
        return result

    def _get_level_label(self, difficulty: str) -> str:
        """Get human-readable level label for a difficulty."""
        labels = {
            "easy": "L5 - Senior SWE",
            "medium": "L6 - Staff Engineer",
            "hard": "L7 - Principal Engineer",
        }
        return labels.get(difficulty, difficulty)

    async def chat_about_design(
        self,
        problem_description: str,
        problem_title: str,
        candidate_message: str,
        conversation_history: list[Dict[str, str]],
        current_schema: Optional[Dict[str, Any]] = None,
        current_api_spec: Optional[Dict[str, Any]] = None,
        current_diagram: Optional[Dict[str, Any]] = None,
        solution_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Chat with a candidate about their system design, providing guidance
        toward a correct solution and evaluating their diagram.

        Args:
            problem_description: The problem being solved
            problem_title: Title of the problem
            candidate_message: The candidate's latest message
            conversation_history: Previous messages in the conversation
            current_schema: Current database schema design (if any)
            current_api_spec: Current API specification (if any)
            current_diagram: Current diagram data (if any)
            solution_reference: Reference solution for guiding candidates

        Returns:
            AI response with feedback and guidance
        """
        # Return mock response in demo mode
        if self.demo_mode:
            return {
                "response": f"""I see you're working on the **{problem_title}** problem. Let me help guide you!

Based on your question, here are some key considerations:

1. **Architecture**: Think about separating concerns - you'll need a service layer, a data layer, and likely a caching layer for high performance.

2. **Database Design**: For this type of system, consider what data you need to store and how it will be queried. Think about indexing strategies.

3. **Scalability**: How will your system handle millions of requests? Consider:
   - Horizontal scaling
   - Caching (Redis is great for this)
   - Database sharding strategies

4. **Reliability**: What happens when components fail? Consider:
   - Graceful degradation
   - Retry mechanisms
   - Circuit breakers

Would you like me to elaborate on any of these points? Or share what you have so far and I can provide specific feedback!

*Demo mode: In production, Claude would provide more detailed, context-specific guidance based on your actual design.*""",
                "diagram_feedback": None,
                "suggested_improvements": [
                    "Consider adding a caching layer",
                    "Think about data partitioning for scale",
                    "Add health check endpoints"
                ],
                "is_on_track": True,
                "demo_mode": True
            }

        # Build the system prompt for design coaching
        system_prompt = f"""You are an expert system design coach helping candidates design distributed systems. Your role is to:

1. **Guide candidates toward a correct solution** - Don't give away the answer directly, but ask probing questions and provide hints that lead them in the right direction.

2. **Evaluate their current design** - If they share a diagram or schema, provide constructive feedback on what's good and what needs improvement.

3. **Be encouraging but honest** - Praise good ideas, but point out potential issues with scalability, reliability, or performance.

4. **Focus on key concepts**:
   - Scalability (horizontal vs vertical, sharding, replication)
   - Reliability (redundancy, failover, graceful degradation)
   - Performance (caching, CDNs, database optimization)
   - Data consistency (CAP theorem, eventual consistency)

5. **Provide specific, actionable feedback** - Don't just say "this is wrong", explain why and suggest alternatives.

6. **Reference the solution requirements** when appropriate to ensure they're meeting all test scenarios.

PROBLEM: {problem_title}
DESCRIPTION:
{problem_description}

REFERENCE SOLUTION (use this to guide the candidate, but don't reveal it directly):
{solution_reference or "A good solution should include proper database schema, caching layer, API design, and consideration for scale and reliability."}

When evaluating diagrams, look for:
- Clear component separation (load balancers, API servers, databases, caches)
- Proper data flow arrows
- Scalability considerations (multiple instances, replicas)
- Caching strategy
- Error handling/failover paths

Respond in a conversational, helpful tone. Use markdown for formatting. Be specific and actionable in your feedback."""

        # Build the conversation context
        messages = []

        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        # Build current context
        current_context = f"**Candidate's message:** {candidate_message}\n\n"

        if current_schema:
            current_context += f"**Current Database Schema:**\n```json\n{json.dumps(current_schema, indent=2)}\n```\n\n"

        if current_api_spec:
            current_context += f"**Current API Specification:**\n```json\n{json.dumps(current_api_spec, indent=2)}\n```\n\n"

        if current_diagram:
            current_context += f"**Current Diagram Data:**\n```json\n{json.dumps(current_diagram, indent=2)}\n```\n\nPlease evaluate the diagram structure and provide feedback on the architecture shown.\n\n"

        messages.append({"role": "user", "content": current_context})

        # Call Claude
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )

        # Track token usage
        self._track_usage(message)

        response_text = message.content[0].text

        # Generate structured response
        result = {
            "response": response_text,
            "diagram_feedback": None,
            "suggested_improvements": [],
            "is_on_track": True,
            "demo_mode": False
        }

        # If there was a diagram, try to extract specific diagram feedback
        if current_diagram:
            # Make a follow-up call for structured diagram feedback
            try:
                diagram_prompt = f"""Analyze this system design diagram and provide structured feedback:

Diagram data:
{json.dumps(current_diagram, indent=2)}

Respond with JSON in this exact format:
{{
    "strengths": ["list of good things about the design"],
    "weaknesses": ["list of issues or missing elements"],
    "suggested_improvements": ["specific actionable improvements"],
    "is_on_track": true/false (is this design heading in the right direction for a {problem_title}?),
    "score": 0-100 (how complete/correct is this design?)
}}"""

                diagram_message = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": diagram_prompt}]
                )

                # Track token usage (adds to previous usage)
                prev_input, prev_output = self._last_input_tokens, self._last_output_tokens
                self._track_usage(diagram_message)
                self._last_input_tokens += prev_input
                self._last_output_tokens += prev_output

                diagram_response = diagram_message.content[0].text
                try:
                    diagram_feedback = json.loads(diagram_response)
                    result["diagram_feedback"] = diagram_feedback
                    result["suggested_improvements"] = diagram_feedback.get("suggested_improvements", [])
                    result["is_on_track"] = diagram_feedback.get("is_on_track", True)
                except json.JSONDecodeError:
                    pass
            except Exception:
                pass

        return result

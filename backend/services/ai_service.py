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
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
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
        services_str = ", ".join(required_services or ["postgres"])

        context = f"""
Problem: {problem_description}

Candidate's Design:
{design_text}

Required Infrastructure Services: {services_str}
"""
        if api_spec:
            context += f"\nAPI Specification:\n{json.dumps(api_spec, indent=2)}"

        system_prompt = """You are an expert Python developer generating FastAPI code.

Generate a complete, working FastAPI application based on the candidate's system design.

Requirements:
1. Use FastAPI with async/await
2. Include proper error handling
3. Use environment variables for service connections (they will be injected):
   - DATABASE_URL for PostgreSQL
   - REDIS_URL for Redis
   - KAFKA_BROKERS for Kafka
   - CASSANDRA_URL for Cassandra
   - MONGODB_URL for MongoDB
   - ELASTICSEARCH_URL for Elasticsearch
4. Include a /health endpoint that returns {"status": "healthy"}
5. Implement the core API endpoints from the design
6. Use proper type hints and Pydantic models
7. Keep the code self-contained in a single file

Return ONLY the Python code, no explanations or markdown code blocks."""

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

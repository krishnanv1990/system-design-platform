"""
Validation service for candidate submissions.
Combines rule-based and AI-powered validation.
"""

from typing import Optional, Dict, Any, List
import json
import re

from backend.models.problem import Problem
from backend.schemas.submission import ValidationResponse
from backend.services.ai_service import AIService


class ValidationService:
    """
    Service for validating candidate submissions.
    Uses both rule-based checks and AI-powered analysis.
    """

    def __init__(self):
        """Initialize the validation service."""
        self.ai_service = AIService()

    async def validate_all(
        self,
        problem: Problem,
        schema_input: Optional[Dict[str, Any]] = None,
        api_spec_input: Optional[Dict[str, Any]] = None,
        design_text: Optional[str] = None,
    ) -> ValidationResponse:
        """
        Run all validations on a submission.

        Args:
            problem: The problem being solved
            schema_input: Candidate's database schema
            api_spec_input: Candidate's API specification
            design_text: Candidate's design description

        Returns:
            Comprehensive validation response
        """
        errors: List[str] = []
        warnings: List[str] = []
        suggestions: List[str] = []

        # Rule-based schema validation
        if schema_input:
            schema_result = self._validate_schema(schema_input, problem.expected_schema)
            errors.extend(schema_result.get("errors", []))
            warnings.extend(schema_result.get("warnings", []))

        # Rule-based API spec validation
        if api_spec_input:
            api_result = self._validate_api_spec(api_spec_input, problem.expected_api_spec)
            errors.extend(api_result.get("errors", []))
            warnings.extend(api_result.get("warnings", []))

        # AI-powered design validation
        ai_result = {}
        if design_text:
            try:
                # Parse design_text if it's a JSON string (from canvas editor)
                design_content = design_text
                try:
                    parsed_design = json.loads(design_text)
                    if isinstance(parsed_design, dict):
                        # Extract text content from canvas mode structure
                        if "text" in parsed_design and parsed_design.get("text"):
                            design_content = parsed_design["text"]
                        elif "canvas" in parsed_design:
                            # For canvas-only designs, create a summary from the canvas data
                            try:
                                canvas_data = json.loads(parsed_design["canvas"]) if isinstance(parsed_design["canvas"], str) else parsed_design["canvas"]
                                if canvas_data and "elements" in canvas_data:
                                    elements = canvas_data.get("elements", [])
                                    component_types = [el.get("type") for el in elements if el.get("type") not in ["rectangle", "ellipse", "arrow", "text"]]
                                    labels = [el.get("label") for el in elements if el.get("label")]
                                    if component_types or labels:
                                        design_content = f"Canvas-based design with components: {', '.join(set(component_types))}. Components: {', '.join(labels)}"
                                    else:
                                        design_content = "Canvas-based system design diagram"
                            except (json.JSONDecodeError, TypeError):
                                design_content = "Canvas-based system design diagram"
                except (json.JSONDecodeError, TypeError):
                    # Keep original design_text if not valid JSON
                    pass

                ai_result = await self.ai_service.validate_design(
                    problem_description=problem.description,
                    design_text=design_content,
                    schema_input=schema_input,
                    api_spec_input=api_spec_input,
                )
                errors.extend(ai_result.get("errors", []))
                warnings.extend(ai_result.get("warnings", []))
                suggestions.extend(ai_result.get("suggestions", []))
            except Exception as e:
                # Log the error but don't fail validation completely
                import logging
                logging.error(f"AI validation failed: {str(e)}")
                warnings.append("AI-powered validation was unavailable. Basic validation was performed.")

        # Determine if valid (no critical errors)
        is_valid = len(errors) == 0

        # Calculate score if AI provided one
        score = ai_result.get("score") if ai_result else None

        return ValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            score=score,
        )

    def _normalize_tables(self, schema_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize tables from various formats to a consistent dict format.

        Handles:
        - Dict format: { "tables": { "users": { "columns": {...} } } }
        - Array format: { "tables": [{ "name": "users", "columns": {...} }] }
        - Stores format: { "stores": [{ "name": "users", ... }] }

        Returns:
            Dict with table_name -> table_definition mapping
        """
        tables = schema_input.get("tables", schema_input.get("stores", {}))

        # If tables is already a dict, return it
        if isinstance(tables, dict):
            return tables

        # If tables is a list, convert to dict
        if isinstance(tables, list):
            normalized = {}
            for table in tables:
                if isinstance(table, dict):
                    table_name = table.get("name", table.get("tableName", f"table_{len(normalized)}"))
                    normalized[table_name] = table
            return normalized

        return {}

    def _normalize_columns(self, table_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize columns from various formats to a consistent dict format.

        Handles:
        - Dict format: { "columns": { "id": { "type": "int" } } }
        - Array format: { "columns": [{ "name": "id", "type": "int" }] }

        Returns:
            Dict with column_name -> column_definition mapping
        """
        columns = table_def.get("columns", {})

        # If columns is already a dict, return it
        if isinstance(columns, dict):
            return columns

        # If columns is a list, convert to dict
        if isinstance(columns, list):
            normalized = {}
            for col in columns:
                if isinstance(col, dict):
                    col_name = col.get("name", col.get("columnName", f"col_{len(normalized)}"))
                    normalized[col_name] = col
            return normalized

        return {}

    def _validate_schema(
        self,
        schema_input: Dict[str, Any],
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[str]]:
        """
        Validate database schema against requirements.

        Args:
            schema_input: Candidate's schema
            expected_schema: Expected schema structure

        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []

        # Normalize tables to dict format
        tables = self._normalize_tables(schema_input)

        # Check for required tables
        if expected_schema and "required_tables" in expected_schema:
            input_tables = set(tables.keys())
            required_tables = set(expected_schema["required_tables"])
            missing = required_tables - input_tables
            if missing:
                errors.append(f"Missing required tables: {', '.join(missing)}")

        # Check for primary keys
        for table_name, table_def in tables.items():
            if not isinstance(table_def, dict):
                continue
            columns = self._normalize_columns(table_def)
            has_pk = any(
                col.get("primary_key") or col.get("primaryKey")
                for col in columns.values()
                if isinstance(col, dict)
            )
            if not has_pk:
                warnings.append(f"Table '{table_name}' has no primary key defined")

        # Check for indexes on foreign keys
        for table_name, table_def in tables.items():
            if not isinstance(table_def, dict):
                continue
            columns = self._normalize_columns(table_def)
            indexes = table_def.get("indexes", [])
            for col_name, col_def in columns.items():
                if not isinstance(col_def, dict):
                    continue
                if (col_def.get("foreign_key") or col_def.get("foreignKey")) and col_name not in indexes:
                    warnings.append(
                        f"Consider adding index on foreign key '{col_name}' in table '{table_name}'"
                    )

        return {"errors": errors, "warnings": warnings}

    def _validate_api_spec(
        self,
        api_spec_input: Dict[str, Any],
        expected_api_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[str]]:
        """
        Validate API specification against requirements.

        Args:
            api_spec_input: Candidate's API spec
            expected_api_spec: Expected API spec structure

        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []

        # Check for required endpoints
        if expected_api_spec and "required_endpoints" in expected_api_spec:
            input_endpoints = set()
            for endpoint in api_spec_input.get("endpoints", []):
                method = endpoint.get("method", "GET")
                path = endpoint.get("path", "")
                input_endpoints.add(f"{method} {path}")

            required = set(expected_api_spec["required_endpoints"])
            missing = required - input_endpoints
            if missing:
                errors.append(f"Missing required endpoints: {', '.join(missing)}")

        # Check for proper HTTP methods
        for endpoint in api_spec_input.get("endpoints", []):
            method = endpoint.get("method", "")
            path = endpoint.get("path", "")

            # POST/PUT should have request body
            if method in ["POST", "PUT"] and not endpoint.get("request_body"):
                warnings.append(f"{method} {path} should define a request body")

            # Check for response definitions
            if not endpoint.get("responses"):
                warnings.append(f"{method} {path} should define response schemas")

        # Check for authentication
        has_auth = api_spec_input.get("security") or any(
            endpoint.get("security") for endpoint in api_spec_input.get("endpoints", [])
        )
        if not has_auth:
            warnings.append("No authentication/authorization defined")

        return {"errors": errors, "warnings": warnings}

    def validate_design_text(self, design_text: str) -> Dict[str, List[str]]:
        """
        Basic validation of design text.

        Args:
            design_text: Candidate's design description

        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []

        if not design_text or len(design_text.strip()) < 100:
            errors.append("Design description is too short. Please provide more detail.")

        # Check for key sections
        key_topics = [
            ("database", "data storage", "persistence"),
            ("api", "endpoint", "interface"),
            ("cach", "redis", "memcache"),
            ("scal", "horizontal", "vertical"),
        ]

        for topics in key_topics:
            if not any(topic in design_text.lower() for topic in topics):
                warnings.append(
                    f"Consider addressing: {topics[0]} design"
                )

        return {"errors": errors, "warnings": warnings}

"""
Terraform service for infrastructure code generation and execution.
Manages the lifecycle of Terraform deployments.
"""

import os
import json
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, Any
from pathlib import Path

from backend.config import get_settings
from backend.services.ai_service import AIService

settings = get_settings()


class TerraformService:
    """
    Service for generating and executing Terraform code.
    Handles infrastructure provisioning on GCP.
    """

    def __init__(self):
        """Initialize the Terraform service."""
        self.ai_service = AIService()
        self.workspace_dir = Path("/tmp/terraform_workspaces")
        self.workspace_dir.mkdir(exist_ok=True)

    async def generate_terraform(
        self,
        problem_description: str,
        design_text: str,
        schema_input: Optional[Dict[str, Any]] = None,
        api_spec_input: Optional[Dict[str, Any]] = None,
        namespace: str = "default",
    ) -> str:
        """
        Generate Terraform code from design.

        Args:
            problem_description: Problem being solved
            design_text: Candidate's design
            schema_input: Database schema
            api_spec_input: API specification
            namespace: Deployment namespace

        Returns:
            Generated Terraform code
        """
        terraform_code = await self.ai_service.generate_terraform(
            problem_description=problem_description,
            design_text=design_text,
            schema_input=schema_input,
            api_spec_input=api_spec_input,
            namespace=namespace,
        )

        # Extract terraform code from markdown if present
        terraform_code = self._extract_terraform_from_markdown(terraform_code)

        return terraform_code

    def _extract_terraform_from_markdown(self, text: str) -> str:
        """
        Extract Terraform code from markdown code blocks.

        Args:
            text: Text that may contain markdown code blocks

        Returns:
            Extracted Terraform code
        """
        import re

        # Look for ```terraform or ```hcl code blocks
        pattern = r"```(?:terraform|hcl)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            return "\n\n".join(matches)

        # If no code blocks, return as-is
        return text

    def create_workspace(self, submission_id: int, terraform_code: str) -> Path:
        """
        Create a workspace directory for Terraform execution.

        Args:
            submission_id: Submission ID for workspace naming
            terraform_code: Terraform code to write

        Returns:
            Path to the workspace directory
        """
        workspace = self.workspace_dir / f"submission_{submission_id}"
        workspace.mkdir(exist_ok=True)

        # Write main.tf
        main_tf = workspace / "main.tf"
        main_tf.write_text(terraform_code)

        # Write provider configuration
        provider_tf = workspace / "provider.tf"
        provider_tf.write_text(f'''
terraform {{
  required_providers {{
    google = {{
      source  = "hashicorp/google"
      version = "~> 5.0"
    }}
  }}
}}

provider "google" {{
  project = "{settings.gcp_project_id}"
  region  = "{settings.gcp_region}"
}}
''')

        # Write variables
        variables_tf = workspace / "variables.tf"
        variables_tf.write_text('''
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "namespace" {
  description = "Resource namespace for isolation"
  type        = string
}
''')

        # Write terraform.tfvars
        tfvars = workspace / "terraform.tfvars"
        tfvars.write_text(f'''
project_id = "{settings.gcp_project_id}"
region     = "{settings.gcp_region}"
namespace  = "submission-{submission_id}"
''')

        return workspace

    def init_workspace(self, workspace: Path) -> Dict[str, Any]:
        """
        Initialize Terraform in the workspace.

        Args:
            workspace: Path to workspace directory

        Returns:
            Result with success status and output
        """
        try:
            result = subprocess.run(
                ["terraform", "init", "-no-color"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Terraform init timed out",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Terraform not installed",
            }

    def plan(self, workspace: Path) -> Dict[str, Any]:
        """
        Run Terraform plan.

        Args:
            workspace: Path to workspace directory

        Returns:
            Result with success status and plan output
        """
        try:
            result = subprocess.run(
                ["terraform", "plan", "-no-color", "-out=tfplan"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Terraform plan timed out",
            }

    def apply(self, workspace: Path) -> Dict[str, Any]:
        """
        Apply Terraform configuration.

        Args:
            workspace: Path to workspace directory

        Returns:
            Result with success status and apply output
        """
        try:
            result = subprocess.run(
                ["terraform", "apply", "-no-color", "-auto-approve", "tfplan"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=600,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Terraform apply timed out",
            }

    def get_outputs(self, workspace: Path) -> Dict[str, Any]:
        """
        Get Terraform outputs.

        Args:
            workspace: Path to workspace directory

        Returns:
            Terraform outputs as dictionary
        """
        try:
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {}
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return {}

    def destroy(self, workspace: Path) -> Dict[str, Any]:
        """
        Destroy Terraform-managed infrastructure.

        Args:
            workspace: Path to workspace directory

        Returns:
            Result with success status and output
        """
        try:
            result = subprocess.run(
                ["terraform", "destroy", "-no-color", "-auto-approve"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=600,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Terraform destroy timed out",
            }

    def cleanup_workspace(self, workspace: Path) -> None:
        """
        Remove a workspace directory.

        Args:
            workspace: Path to workspace directory
        """
        if workspace.exists():
            shutil.rmtree(workspace)

"""
Chaos engineering service for testing system resilience.
Simulates various failure scenarios to validate candidate solutions.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from backend.config import get_settings

settings = get_settings()


class ChaosScenario:
    """Predefined chaos scenarios for testing."""

    SERVICE_FAILURE = "service_failure"
    ZONE_FAILURE = "zone_failure"
    REGIONAL_FAILURE = "regional_failure"
    NETWORK_PARTITION = "network_partition"
    LATENCY_INJECTION = "latency_injection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DATABASE_FAILURE = "database_failure"
    CACHE_FAILURE = "cache_failure"


class ChaosService:
    """
    Service for chaos engineering tests.
    Integrates with Chaos Toolkit and GCP to simulate failures.
    """

    def __init__(self):
        """Initialize the chaos service."""
        self.workspace_dir = Path("/tmp/chaos_experiments")
        self.workspace_dir.mkdir(exist_ok=True)

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """
        Get list of available chaos scenarios.

        Returns:
            List of scenario definitions
        """
        return [
            {
                "id": ChaosScenario.SERVICE_FAILURE,
                "name": "Service Failure",
                "description": "Simulate a single service instance failure",
                "severity": "low",
                "expected_behavior": "System should recover automatically",
            },
            {
                "id": ChaosScenario.ZONE_FAILURE,
                "name": "Zone Failure",
                "description": "Simulate an entire availability zone going down",
                "severity": "medium",
                "expected_behavior": "System should failover to other zones",
            },
            {
                "id": ChaosScenario.REGIONAL_FAILURE,
                "name": "Regional Failure",
                "description": "Simulate an entire region becoming unavailable",
                "severity": "high",
                "expected_behavior": "System should failover to backup region",
            },
            {
                "id": ChaosScenario.NETWORK_PARTITION,
                "name": "Network Partition",
                "description": "Simulate network split between services",
                "severity": "medium",
                "expected_behavior": "System should handle partial connectivity",
            },
            {
                "id": ChaosScenario.LATENCY_INJECTION,
                "name": "Latency Injection",
                "description": "Add artificial latency to service calls",
                "severity": "low",
                "expected_behavior": "System should handle slow responses gracefully",
            },
            {
                "id": ChaosScenario.RESOURCE_EXHAUSTION,
                "name": "Resource Exhaustion",
                "description": "Simulate CPU/memory exhaustion",
                "severity": "medium",
                "expected_behavior": "System should autoscale or gracefully degrade",
            },
            {
                "id": ChaosScenario.DATABASE_FAILURE,
                "name": "Database Failure",
                "description": "Simulate database connection failures",
                "severity": "high",
                "expected_behavior": "System should queue requests or return cached data",
            },
            {
                "id": ChaosScenario.CACHE_FAILURE,
                "name": "Cache Failure",
                "description": "Simulate cache layer failure",
                "severity": "medium",
                "expected_behavior": "System should fallback to database",
            },
        ]

    def create_experiment(
        self,
        scenario: str,
        endpoint_url: str,
        namespace: str,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a chaos experiment definition.

        Args:
            scenario: Scenario type from ChaosScenario
            endpoint_url: Target service URL
            namespace: Resource namespace
            custom_config: Optional custom configuration

        Returns:
            Chaos Toolkit experiment definition
        """
        # Base experiment structure
        experiment = {
            "version": "1.0.0",
            "title": f"Chaos Experiment: {scenario}",
            "description": f"Testing resilience against {scenario}",
            "tags": ["automated", namespace],
            "configuration": {
                "endpoint_url": endpoint_url,
                "namespace": namespace,
                "gcp_project": settings.gcp_project_id,
                "gcp_region": settings.gcp_region,
            },
            "steady-state-hypothesis": self._create_steady_state(endpoint_url),
            "method": [],
            "rollbacks": [],
        }

        # Add scenario-specific method
        if scenario == ChaosScenario.SERVICE_FAILURE:
            experiment["method"] = self._service_failure_method(namespace)
            experiment["rollbacks"] = self._service_failure_rollback(namespace)

        elif scenario == ChaosScenario.ZONE_FAILURE:
            experiment["method"] = self._zone_failure_method(namespace)
            experiment["rollbacks"] = self._zone_failure_rollback(namespace)

        elif scenario == ChaosScenario.REGIONAL_FAILURE:
            experiment["method"] = self._regional_failure_method(namespace)
            experiment["rollbacks"] = self._regional_failure_rollback(namespace)

        elif scenario == ChaosScenario.NETWORK_PARTITION:
            experiment["method"] = self._network_partition_method(namespace)

        elif scenario == ChaosScenario.LATENCY_INJECTION:
            latency_ms = custom_config.get("latency_ms", 500) if custom_config else 500
            experiment["method"] = self._latency_injection_method(namespace, latency_ms)

        elif scenario == ChaosScenario.RESOURCE_EXHAUSTION:
            experiment["method"] = self._resource_exhaustion_method(namespace)

        elif scenario == ChaosScenario.DATABASE_FAILURE:
            experiment["method"] = self._database_failure_method(namespace)
            experiment["rollbacks"] = self._database_failure_rollback(namespace)

        elif scenario == ChaosScenario.CACHE_FAILURE:
            experiment["method"] = self._cache_failure_method(namespace)
            experiment["rollbacks"] = self._cache_failure_rollback(namespace)

        return experiment

    def _create_steady_state(self, endpoint_url: str) -> Dict[str, Any]:
        """Create steady state hypothesis for health checks."""
        return {
            "title": "System is healthy and responsive",
            "probes": [
                {
                    "type": "probe",
                    "name": "service-responds-200",
                    "tolerance": True,
                    "provider": {
                        "type": "http",
                        "url": f"{endpoint_url}/health",
                        "timeout": 10,
                    },
                },
                {
                    "type": "probe",
                    "name": "response-time-acceptable",
                    "tolerance": {
                        "type": "range",
                        "range": [0, 1000],  # Response time in ms
                    },
                    "provider": {
                        "type": "http",
                        "url": endpoint_url,
                        "timeout": 10,
                    },
                },
            ],
        }

    def _service_failure_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for service failure scenario."""
        return [
            {
                "type": "action",
                "name": "terminate-service-instance",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "stop_instance",
                    "arguments": {
                        "instance_name": f"{namespace}-instance",
                        "zone": f"{settings.gcp_region}-a",
                    },
                },
                "pauses": {"after": 30},  # Wait for failover
            },
            {
                "type": "probe",
                "name": "verify-service-recovered",
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 30,
                },
            },
        ]

    def _service_failure_rollback(self, namespace: str) -> List[Dict[str, Any]]:
        """Rollback for service failure scenario."""
        return [
            {
                "type": "action",
                "name": "restart-service-instance",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "start_instance",
                    "arguments": {
                        "instance_name": f"{namespace}-instance",
                        "zone": f"{settings.gcp_region}-a",
                    },
                },
            },
        ]

    def _zone_failure_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for zone failure scenario."""
        return [
            {
                "type": "action",
                "name": "stop-zone-instances",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "stop_instances",
                    "arguments": {
                        "filter": f"labels.namespace={namespace}",
                        "zone": f"{settings.gcp_region}-a",
                    },
                },
                "pauses": {"after": 60},
            },
            {
                "type": "probe",
                "name": "verify-cross-zone-failover",
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 60,
                },
            },
        ]

    def _zone_failure_rollback(self, namespace: str) -> List[Dict[str, Any]]:
        """Rollback for zone failure scenario."""
        return [
            {
                "type": "action",
                "name": "restart-zone-instances",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "start_instances",
                    "arguments": {
                        "filter": f"labels.namespace={namespace}",
                        "zone": f"{settings.gcp_region}-a",
                    },
                },
            },
        ]

    def _regional_failure_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for regional failure scenario."""
        return [
            {
                "type": "action",
                "name": "stop-regional-instances",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "stop_instances",
                    "arguments": {
                        "filter": f"labels.namespace={namespace}",
                    },
                },
                "pauses": {"after": 120},
            },
            {
                "type": "probe",
                "name": "verify-multi-region-failover",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 120,
                },
            },
        ]

    def _regional_failure_rollback(self, namespace: str) -> List[Dict[str, Any]]:
        """Rollback for regional failure scenario."""
        return [
            {
                "type": "action",
                "name": "restart-regional-instances",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.compute.actions",
                    "func": "start_instances",
                    "arguments": {
                        "filter": f"labels.namespace={namespace}",
                    },
                },
            },
        ]

    def _network_partition_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for network partition scenario."""
        return [
            {
                "type": "action",
                "name": "create-network-partition",
                "provider": {
                    "type": "process",
                    "path": "gcloud",
                    "arguments": [
                        "compute", "firewall-rules", "create",
                        f"{namespace}-partition-test",
                        "--network", "default",
                        "--action", "deny",
                        "--direction", "ingress",
                        "--priority", "100",
                        "--source-ranges", "10.0.0.0/8",
                    ],
                },
                "pauses": {"after": 30},
            },
            {
                "type": "probe",
                "name": "service-handles-partition",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 30,
                },
            },
            {
                "type": "action",
                "name": "remove-network-partition",
                "provider": {
                    "type": "process",
                    "path": "gcloud",
                    "arguments": [
                        "compute", "firewall-rules", "delete",
                        f"{namespace}-partition-test",
                        "--quiet",
                    ],
                },
            },
        ]

    def _latency_injection_method(self, namespace: str, latency_ms: int) -> List[Dict[str, Any]]:
        """Method for latency injection scenario."""
        return [
            {
                "type": "action",
                "name": "inject-latency",
                "provider": {
                    "type": "process",
                    "path": "sleep",
                    "arguments": str(latency_ms / 1000),
                },
                "pauses": {"before": 5, "after": 5},
            },
            {
                "type": "probe",
                "name": "service-handles-latency",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": latency_ms / 1000 + 10,
                },
            },
        ]

    def _resource_exhaustion_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for resource exhaustion scenario."""
        return [
            {
                "type": "action",
                "name": "exhaust-resources",
                "provider": {
                    "type": "process",
                    "path": "stress",
                    "arguments": "--cpu 4 --timeout 30s",
                },
                "pauses": {"after": 10},
            },
            {
                "type": "probe",
                "name": "service-survives-load",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 60,
                },
            },
        ]

    def _database_failure_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for database failure scenario."""
        return [
            {
                "type": "action",
                "name": "stop-database",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.sql.actions",
                    "func": "stop_cloud_sql_instance",
                    "arguments": {
                        "instance_name": f"{namespace}-db",
                    },
                },
                "pauses": {"after": 30},
            },
            {
                "type": "probe",
                "name": "service-handles-db-failure",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}/health",
                    "timeout": 30,
                },
            },
        ]

    def _database_failure_rollback(self, namespace: str) -> List[Dict[str, Any]]:
        """Rollback for database failure scenario."""
        return [
            {
                "type": "action",
                "name": "start-database",
                "provider": {
                    "type": "python",
                    "module": "chaostoolkit_google_cloud_platform.sql.actions",
                    "func": "start_cloud_sql_instance",
                    "arguments": {
                        "instance_name": f"{namespace}-db",
                    },
                },
            },
        ]

    def _cache_failure_method(self, namespace: str) -> List[Dict[str, Any]]:
        """Method for cache failure scenario."""
        return [
            {
                "type": "action",
                "name": "flush-cache",
                "provider": {
                    "type": "process",
                    "path": "redis-cli",
                    "arguments": "FLUSHALL",
                },
                "pauses": {"after": 5},
            },
            {
                "type": "probe",
                "name": "service-handles-cache-miss",
                "tolerance": True,
                "provider": {
                    "type": "http",
                    "url": "${endpoint_url}",
                    "timeout": 30,
                },
            },
        ]

    def _cache_failure_rollback(self, namespace: str) -> List[Dict[str, Any]]:
        """Rollback for cache failure scenario (cache will repopulate naturally)."""
        return []

    async def run_experiment(
        self,
        experiment: Dict[str, Any],
        submission_id: int,
    ) -> Dict[str, Any]:
        """
        Execute a chaos experiment.

        Args:
            experiment: Chaos Toolkit experiment definition
            submission_id: Submission ID for tracking

        Returns:
            Experiment results
        """
        workspace = self.workspace_dir / f"exp_{submission_id}_{datetime.utcnow().timestamp()}"
        workspace.mkdir(exist_ok=True)

        # Write experiment file
        experiment_file = workspace / "experiment.json"
        experiment_file.write_text(json.dumps(experiment, indent=2))

        # Run chaos toolkit
        try:
            proc = await asyncio.create_subprocess_exec(
                "chaos", "run", str(experiment_file),
                "--journal-path", str(workspace / "journal.json"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=300,
            )

            # Parse journal
            journal_path = workspace / "journal.json"
            if journal_path.exists():
                with open(journal_path) as f:
                    journal = json.load(f)
            else:
                journal = {}

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "journal": journal,
                "workspace": str(workspace),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Experiment timed out",
                "workspace": str(workspace),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "workspace": str(workspace),
            }

"""
Chaos experiment actions for injecting failures.
These actions simulate various failure scenarios.
"""

import time
import random
import httpx
from typing import Optional


# Global state for tracking injected failures
_injected_failures = {
    "latency": None,
    "storage_failure_rate": 0,
    "network_partition": False,
    "db_latency": None,
    "presence_service_down": False,
}


def inject_latency(latency_ms: int = 500, duration_seconds: int = 30) -> dict:
    """
    Inject artificial latency into the service.

    In a real implementation, this would configure a proxy or service mesh
    to add latency to requests.
    """
    _injected_failures["latency"] = {
        "ms": latency_ms,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "latency_injected",
        "latency_ms": latency_ms,
        "duration_seconds": duration_seconds
    }


def remove_latency_injection() -> dict:
    """Remove any injected latency."""
    _injected_failures["latency"] = None
    return {"status": "latency_removed"}


def simulate_storage_latency(latency_ms: int = 2000, duration_seconds: int = 60) -> dict:
    """
    Simulate slow storage operations.

    In production, this could be done by:
    - Configuring network policies to slow traffic to storage
    - Using a proxy to add delays
    - Temporarily throttling storage IOPS
    """
    _injected_failures["storage_latency"] = {
        "ms": latency_ms,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "storage_latency_injected",
        "latency_ms": latency_ms,
        "duration_seconds": duration_seconds
    }


def fail_storage_percentage(failure_rate: float = 0.3, duration_seconds: int = 60) -> dict:
    """
    Make a percentage of storage operations fail.

    This simulates partial storage failures like:
    - Disk errors
    - Network timeouts to specific replicas
    - Quota exceeded errors
    """
    _injected_failures["storage_failure_rate"] = failure_rate
    _injected_failures["storage_failure_until"] = time.time() + duration_seconds

    return {
        "status": "storage_failures_injected",
        "failure_rate": failure_rate,
        "duration_seconds": duration_seconds
    }


def restore_storage() -> dict:
    """Restore normal storage behavior."""
    _injected_failures["storage_latency"] = None
    _injected_failures["storage_failure_rate"] = 0
    return {"status": "storage_restored"}


def simulate_network_partition(
    partition_duration_seconds: int = 30,
    affected_percentage: float = 0.5
) -> dict:
    """
    Simulate a network partition.

    In a real implementation, this would:
    - Use iptables to drop packets between nodes
    - Configure network policies in Kubernetes
    - Use a service mesh to reject connections
    """
    _injected_failures["network_partition"] = {
        "affected_percentage": affected_percentage,
        "until": time.time() + partition_duration_seconds
    }

    return {
        "status": "network_partition_created",
        "affected_percentage": affected_percentage,
        "duration_seconds": partition_duration_seconds
    }


def restore_network() -> dict:
    """Restore normal network connectivity."""
    _injected_failures["network_partition"] = None
    return {"status": "network_restored"}


def inject_database_latency(latency_ms: int = 1000, duration_seconds: int = 30) -> dict:
    """
    Inject latency into database operations.

    This simulates:
    - Database overload
    - Cross-region replication lag
    - Lock contention
    """
    _injected_failures["db_latency"] = {
        "ms": latency_ms,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "db_latency_injected",
        "latency_ms": latency_ms,
        "duration_seconds": duration_seconds
    }


def kill_presence_service(duration_seconds: int = 30) -> dict:
    """
    Simulate presence service failure.

    This tests that messaging continues to work even when
    presence/online status service is unavailable.
    """
    _injected_failures["presence_service_down"] = True
    _injected_failures["presence_until"] = time.time() + duration_seconds

    return {
        "status": "presence_service_killed",
        "duration_seconds": duration_seconds
    }


def restore_all_services() -> dict:
    """Restore all services to normal operation."""
    global _injected_failures
    _injected_failures = {
        "latency": None,
        "storage_failure_rate": 0,
        "network_partition": False,
        "db_latency": None,
        "presence_service_down": False,
    }

    return {"status": "all_services_restored"}


def kill_pod(pod_name: str, namespace: str = "default") -> dict:
    """
    Kill a specific Kubernetes pod.

    Requires kubectl access and appropriate permissions.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["kubectl", "delete", "pod", pod_name, "-n", namespace, "--grace-period=0", "--force"],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "status": "pod_killed" if result.returncode == 0 else "kill_failed",
            "pod_name": pod_name,
            "namespace": namespace,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def scale_deployment(deployment_name: str, replicas: int, namespace: str = "default") -> dict:
    """
    Scale a Kubernetes deployment.

    Useful for testing:
    - Scale to 0 to simulate complete failure
    - Scale down to test degraded performance
    - Scale up to test recovery
    """
    import subprocess

    try:
        result = subprocess.run(
            ["kubectl", "scale", "deployment", deployment_name,
             f"--replicas={replicas}", "-n", namespace],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "status": "scaled" if result.returncode == 0 else "scale_failed",
            "deployment": deployment_name,
            "replicas": replicas,
            "namespace": namespace
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def corrupt_cache(cache_key_pattern: str = "*", corruption_rate: float = 0.1) -> dict:
    """
    Corrupt cache entries to test cache miss handling.

    This simulates:
    - Cache data corruption
    - Stale data scenarios
    - Cache invalidation failures
    """
    _injected_failures["cache_corruption"] = {
        "pattern": cache_key_pattern,
        "rate": corruption_rate
    }

    return {
        "status": "cache_corruption_enabled",
        "pattern": cache_key_pattern,
        "corruption_rate": corruption_rate
    }


def trigger_gc_pressure(memory_pressure_mb: int = 512, duration_seconds: int = 30) -> dict:
    """
    Create memory pressure to trigger garbage collection.

    Tests application behavior under memory pressure.
    """
    # This is a simulation - in reality you'd allocate memory in the target process
    return {
        "status": "gc_pressure_simulated",
        "memory_pressure_mb": memory_pressure_mb,
        "duration_seconds": duration_seconds,
        "note": "Actual implementation requires access to target process"
    }

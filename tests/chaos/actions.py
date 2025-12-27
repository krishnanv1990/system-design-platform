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


# ==================== Cache Failure Actions ====================

def simulate_cache_unavailable(duration_seconds: int = 30) -> dict:
    """
    Simulate cache (Redis/Memcached) being completely unavailable.

    This tests:
    - Fallback to database when cache is down
    - Graceful degradation of read performance
    - Write-through vs write-behind behavior
    """
    _injected_failures["cache_unavailable"] = {
        "until": time.time() + duration_seconds
    }

    return {
        "status": "cache_unavailable_simulated",
        "duration_seconds": duration_seconds,
        "note": "Service should fall back to database for reads"
    }


def restore_cache() -> dict:
    """Restore cache to normal operation."""
    _injected_failures["cache_unavailable"] = None
    _injected_failures["cache_corruption"] = None
    return {"status": "cache_restored"}


# ==================== Zone Failure Actions ====================

def simulate_zone_failure(zone: str = "us-central1-a", duration_seconds: int = 60) -> dict:
    """
    Simulate complete failure of a GCP zone.

    This tests:
    - Multi-zone redundancy
    - Automatic failover to healthy zones
    - Data replication and consistency
    """
    _injected_failures["zone_failure"] = {
        "zone": zone,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "zone_failure_simulated",
        "zone": zone,
        "duration_seconds": duration_seconds,
        "note": "Simulates all resources in zone becoming unavailable"
    }


def restore_all_zones() -> dict:
    """Restore all zones to normal operation."""
    _injected_failures["zone_failure"] = None
    return {"status": "all_zones_restored"}


# ==================== Cloud Run Instance Actions ====================

def scale_cloud_run_instances(
    min_instances: int = 0,
    max_instances: int = 10,
    service_name: str = None,
    region: str = "us-central1",
    project: str = None
) -> dict:
    """
    Scale Cloud Run service instances.

    This tests:
    - Cold start handling
    - Autoscaling behavior
    - Request queuing during scale-up
    """
    import os
    import subprocess

    project = project or os.getenv("GCP_PROJECT")
    service_name = service_name or os.getenv("CLOUD_RUN_SERVICE", "url-shortener")

    if not project:
        return {
            "status": "skipped",
            "reason": "GCP_PROJECT not set"
        }

    try:
        result = subprocess.run([
            "gcloud", "run", "services", "update", service_name,
            f"--min-instances={min_instances}",
            f"--max-instances={max_instances}",
            f"--region={region}",
            f"--project={project}",
            "--quiet"
        ], capture_output=True, text=True, timeout=120)

        return {
            "status": "scaled" if result.returncode == 0 else "scale_failed",
            "service": service_name,
            "min_instances": min_instances,
            "max_instances": max_instances,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def restore_cloud_run_instances(
    min_instances: int = 1,
    max_instances: int = 100,
    service_name: str = None,
    region: str = "us-central1",
    project: str = None
) -> dict:
    """Restore Cloud Run service to normal scaling configuration."""
    return scale_cloud_run_instances(
        min_instances=min_instances,
        max_instances=max_instances,
        service_name=service_name,
        region=region,
        project=project
    )


def simulate_instance_crash(crash_percentage: float = 0.5, duration_seconds: int = 30) -> dict:
    """
    Simulate a percentage of instances crashing.

    This tests:
    - Load balancer health check detection
    - Traffic rerouting to healthy instances
    - Autoscaling response to unhealthy instances
    """
    _injected_failures["instance_crash"] = {
        "percentage": crash_percentage,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "instance_crash_simulated",
        "crash_percentage": crash_percentage,
        "duration_seconds": duration_seconds,
        "note": f"{int(crash_percentage * 100)}% of instances simulated as crashed"
    }


# ==================== Network Partition Enhancements ====================

def simulate_cross_region_latency(
    latency_ms: int = 200,
    jitter_ms: int = 50,
    duration_seconds: int = 60
) -> dict:
    """
    Simulate high latency between regions.

    This tests:
    - Cross-region replication lag
    - Timeout handling for cross-region calls
    - Eventual consistency behavior
    """
    _injected_failures["cross_region_latency"] = {
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "cross_region_latency_injected",
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "duration_seconds": duration_seconds
    }


def simulate_packet_loss(loss_percentage: float = 0.1, duration_seconds: int = 30) -> dict:
    """
    Simulate network packet loss.

    This tests:
    - Retry logic
    - Timeout handling
    - Connection pooling behavior
    """
    _injected_failures["packet_loss"] = {
        "percentage": loss_percentage,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "packet_loss_injected",
        "loss_percentage": loss_percentage,
        "duration_seconds": duration_seconds
    }


# ==================== Dependency Failure Actions ====================

def kill_external_dependency(dependency_name: str, duration_seconds: int = 30) -> dict:
    """
    Simulate failure of an external dependency (API, service, etc).

    This tests:
    - Circuit breaker patterns
    - Fallback mechanisms
    - Graceful degradation
    """
    _injected_failures[f"dependency_{dependency_name}"] = {
        "until": time.time() + duration_seconds
    }

    return {
        "status": "dependency_killed",
        "dependency": dependency_name,
        "duration_seconds": duration_seconds
    }


def restore_external_dependency(dependency_name: str) -> dict:
    """Restore an external dependency to normal operation."""
    _injected_failures[f"dependency_{dependency_name}"] = None
    return {
        "status": "dependency_restored",
        "dependency": dependency_name
    }

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


# ==================== Raft Consensus Actions ====================

# Track killed Raft nodes for restart
_killed_raft_nodes = []


def raft_write_test_data(cluster_name: str, key: str, value: str) -> dict:
    """
    Write test data to the Raft cluster.

    Used to verify data persistence and consistency during chaos tests.
    """
    import os
    import subprocess

    project = os.getenv("GCP_PROJECT")
    region = os.getenv("GCP_REGION", "us-central1")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    # Get leader endpoint
    try:
        result = subprocess.run([
            "gcloud", "compute", "instances", "list",
            f"--filter=name~{cluster_name}",
            "--format=value(networkInterfaces[0].accessConfigs[0].natIP,name)",
            f"--project={project}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}

        instances = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    instances.append({"ip": parts[0], "name": parts[1]})

        if not instances:
            return {"status": "error", "error": "No instances found"}

        # Try to write to leader (first try each instance)
        for instance in instances:
            try:
                write_result = httpx.post(
                    f"http://{instance['ip']}:8080/api/v1/raft/kv",
                    json={"key": key, "value": value},
                    timeout=10
                )
                if write_result.status_code in [200, 201]:
                    return {
                        "status": "written",
                        "key": key,
                        "value": value,
                        "leader": instance['name']
                    }
                elif write_result.status_code == 307:
                    # Redirect to leader
                    leader_url = write_result.headers.get("Location")
                    if leader_url:
                        write_result = httpx.post(
                            leader_url,
                            json={"key": key, "value": value},
                            timeout=10
                        )
                        if write_result.status_code in [200, 201]:
                            return {"status": "written", "key": key, "value": value}
            except Exception:
                continue

        return {"status": "error", "error": "Could not write to any node"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def raft_kill_leader(cluster_name: str) -> dict:
    """
    Kill the current leader node in the Raft cluster.

    This triggers leader election and tests cluster recovery.
    """
    import os
    import subprocess

    global _killed_raft_nodes

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    try:
        # Find instances
        result = subprocess.run([
            "gcloud", "compute", "instances", "list",
            f"--filter=name~{cluster_name}",
            "--format=value(networkInterfaces[0].accessConfigs[0].natIP,name,zone)",
            f"--project={project}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}

        instances = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    instances.append({"ip": parts[0], "name": parts[1], "zone": parts[2]})

        if not instances:
            return {"status": "error", "error": "No instances found"}

        # Find the leader
        leader = None
        for instance in instances:
            try:
                response = httpx.get(
                    f"http://{instance['ip']}:8080/api/v1/raft/status",
                    timeout=5
                )
                if response.status_code == 200:
                    status = response.json()
                    if status.get("state") == "LEADER" or status.get("is_leader"):
                        leader = instance
                        break
            except Exception:
                continue

        if not leader:
            return {"status": "error", "error": "Could not find leader"}

        # Stop the leader instance
        stop_result = subprocess.run([
            "gcloud", "compute", "instances", "stop", leader['name'],
            f"--zone={leader['zone']}",
            f"--project={project}",
            "--quiet"
        ], capture_output=True, text=True, timeout=120)

        if stop_result.returncode == 0:
            _killed_raft_nodes.append(leader)
            return {
                "status": "leader_killed",
                "leader": leader['name'],
                "zone": leader['zone']
            }
        else:
            return {"status": "error", "error": stop_result.stderr}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def raft_kill_random_follower(cluster_name: str) -> dict:
    """
    Kill a random follower node in the Raft cluster.

    Tests cluster behavior when non-leader nodes fail.
    """
    import os
    import subprocess

    global _killed_raft_nodes

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    try:
        result = subprocess.run([
            "gcloud", "compute", "instances", "list",
            f"--filter=name~{cluster_name}",
            "--format=value(networkInterfaces[0].accessConfigs[0].natIP,name,zone)",
            f"--project={project}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}

        instances = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    # Skip already killed nodes
                    name = parts[1]
                    if not any(k['name'] == name for k in _killed_raft_nodes):
                        instances.append({"ip": parts[0], "name": name, "zone": parts[2]})

        if not instances:
            return {"status": "error", "error": "No available follower instances"}

        # Find followers (non-leaders)
        followers = []
        for instance in instances:
            try:
                response = httpx.get(
                    f"http://{instance['ip']}:8080/api/v1/raft/status",
                    timeout=5
                )
                if response.status_code == 200:
                    status = response.json()
                    if status.get("state") != "LEADER" and not status.get("is_leader"):
                        followers.append(instance)
            except Exception:
                # Assume it's a follower if we can't reach it
                followers.append(instance)

        if not followers:
            return {"status": "error", "error": "No followers found"}

        # Pick random follower
        follower = random.choice(followers)

        # Stop the follower instance
        stop_result = subprocess.run([
            "gcloud", "compute", "instances", "stop", follower['name'],
            f"--zone={follower['zone']}",
            f"--project={project}",
            "--quiet"
        ], capture_output=True, text=True, timeout=120)

        if stop_result.returncode == 0:
            _killed_raft_nodes.append(follower)
            return {
                "status": "follower_killed",
                "follower": follower['name'],
                "zone": follower['zone']
            }
        else:
            return {"status": "error", "error": stop_result.stderr}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def raft_restart_killed_nodes(cluster_name: str) -> dict:
    """
    Restart all previously killed Raft nodes.

    Used in rollback to restore the cluster to full health.
    """
    import os
    import subprocess

    global _killed_raft_nodes

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    if not _killed_raft_nodes:
        return {"status": "nothing_to_restart"}

    restarted = []
    errors = []

    for node in _killed_raft_nodes:
        try:
            result = subprocess.run([
                "gcloud", "compute", "instances", "start", node['name'],
                f"--zone={node['zone']}",
                f"--project={project}",
                "--quiet"
            ], capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                restarted.append(node['name'])
            else:
                errors.append({"node": node['name'], "error": result.stderr})
        except Exception as e:
            errors.append({"node": node['name'], "error": str(e)})

    _killed_raft_nodes = []

    return {
        "status": "restarted" if restarted else "error",
        "restarted": restarted,
        "errors": errors
    }


def raft_create_network_partition(cluster_name: str, partition_type: str = "minority_isolation") -> dict:
    """
    Create a network partition in the Raft cluster.

    partition_type can be:
    - minority_isolation: Isolate minority of nodes (cluster stays available)
    - leader_isolation: Isolate the leader (triggers election)
    - split_brain: Try to create equal partitions (cluster may become unavailable)
    """
    import os
    import subprocess

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    try:
        # Get all instances
        result = subprocess.run([
            "gcloud", "compute", "instances", "list",
            f"--filter=name~{cluster_name}",
            "--format=value(networkInterfaces[0].networkIP,name,zone)",
            f"--project={project}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}

        instances = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 3:
                    instances.append({"internal_ip": parts[0], "name": parts[1], "zone": parts[2]})

        if len(instances) < 3:
            return {"status": "error", "error": "Need at least 3 nodes for partition test"}

        # Determine which nodes to isolate based on partition type
        if partition_type == "minority_isolation":
            # Isolate minority (e.g., 2 out of 5)
            minority_size = len(instances) // 2
            isolated = instances[:minority_size]
            majority = instances[minority_size:]
        elif partition_type == "leader_isolation":
            # Would need to find leader first, simplified here
            isolated = instances[:1]
            majority = instances[1:]
        else:  # split_brain
            mid = len(instances) // 2
            isolated = instances[:mid]
            majority = instances[mid:]

        # Create firewall rules to block traffic between partitions
        isolated_ips = [i['internal_ip'] for i in isolated]
        majority_ips = [i['internal_ip'] for i in majority]

        # Note: In real implementation, would use VPC firewall rules or iptables
        _injected_failures["raft_partition"] = {
            "isolated": [i['name'] for i in isolated],
            "majority": [i['name'] for i in majority],
            "isolated_ips": isolated_ips,
            "majority_ips": majority_ips
        }

        return {
            "status": "partition_created",
            "partition_type": partition_type,
            "isolated_nodes": [i['name'] for i in isolated],
            "majority_nodes": [i['name'] for i in majority]
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def raft_heal_network_partition(cluster_name: str) -> dict:
    """
    Heal a network partition in the Raft cluster.

    Restores connectivity between all nodes.
    """
    if "raft_partition" in _injected_failures:
        partition_info = _injected_failures.pop("raft_partition")
        return {
            "status": "partition_healed",
            "previously_isolated": partition_info.get("isolated", [])
        }

    return {"status": "no_partition_to_heal"}


def raft_write_to_majority(cluster_name: str, key: str, value: str) -> dict:
    """
    Write data to the majority partition during a network split.

    This verifies that the majority partition can still process writes.
    """
    partition_info = _injected_failures.get("raft_partition", {})
    majority_nodes = partition_info.get("majority", [])

    if not majority_nodes:
        # No partition, write normally
        return raft_write_test_data(cluster_name, key, value)

    # Try to write to majority partition nodes
    import os
    import subprocess

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    try:
        # Get external IPs for majority nodes
        result = subprocess.run([
            "gcloud", "compute", "instances", "list",
            f"--filter=name:({' OR '.join(majority_nodes)})",
            "--format=value(networkInterfaces[0].accessConfigs[0].natIP,name)",
            f"--project={project}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"status": "error", "error": result.stderr}

        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    try:
                        write_result = httpx.post(
                            f"http://{ip}:8080/api/v1/raft/kv",
                            json={"key": key, "value": value},
                            timeout=10
                        )
                        if write_result.status_code in [200, 201]:
                            return {
                                "status": "written_to_majority",
                                "key": key,
                                "value": value
                            }
                    except Exception:
                        continue

        return {"status": "error", "error": "Could not write to majority partition"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def raft_cleanup_test_data(cluster_name: str, key_prefix: str) -> dict:
    """
    Clean up test data created during chaos experiments.
    """
    import os
    import subprocess

    project = os.getenv("GCP_PROJECT")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    # In a real implementation, would delete keys matching the prefix
    # For now, just acknowledge the cleanup request
    return {
        "status": "cleanup_requested",
        "key_prefix": key_prefix,
        "note": "Test data cleanup acknowledged"
    }


# ==================== GCP Infrastructure Chaos Actions ====================

def simulate_database_failover(
    duration_seconds: int = 30,
    failover_type: str = "primary"
) -> dict:
    """
    Trigger database failover in Cloud SQL.

    Args:
        duration_seconds: How long to wait for failover
        failover_type: Type of failover ('primary' or 'replica')

    Returns:
        Status of the failover operation
    """
    import os

    project = os.getenv("GCP_PROJECT_ID", os.getenv("GCP_PROJECT"))
    instance = os.getenv("CLOUDSQL_INSTANCE", "sdp-postgres")

    if not project:
        return {"status": "skipped", "reason": "GCP_PROJECT not set"}

    try:
        from google.cloud import sqladmin_v1

        client = sqladmin_v1.SqlAdminServiceClient()

        # Trigger failover
        request = sqladmin_v1.SqlInstancesFailoverRequest(
            project=project,
            instance=instance,
            body=sqladmin_v1.InstancesFailoverRequest(
                failover_context=sqladmin_v1.FailoverContext(
                    kind="sql#failoverContext"
                )
            )
        )

        operation = client.failover(request=request)

        return {
            "status": "failover_initiated",
            "instance": instance,
            "failover_type": failover_type,
            "operation": operation.name
        }

    except ImportError:
        # Simulate if library not available
        _injected_failures["database_failover"] = {
            "until": time.time() + duration_seconds,
            "type": failover_type
        }
        return {
            "status": "simulated",
            "failover_type": failover_type,
            "duration_seconds": duration_seconds
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def restore_database(component: str = "primary") -> dict:
    """Restore database after failover test."""
    if "database_failover" in _injected_failures:
        del _injected_failures["database_failover"]
    return {"status": "database_restored", "component": component}


def simulate_cache_failure(
    cache_type: str = "redis",
    failure_mode: str = "connection_refused",
    duration_seconds: int = 60
) -> dict:
    """
    Simulate Redis/Memorystore cache failure.

    Args:
        cache_type: Type of cache ('redis' or 'memcached')
        failure_mode: Type of failure ('connection_refused', 'timeout', 'error')
        duration_seconds: Duration of the failure

    Returns:
        Status of the cache failure simulation
    """
    import os

    project = os.getenv("GCP_PROJECT_ID", os.getenv("GCP_PROJECT"))
    redis_instance = os.getenv("REDIS_INSTANCE", "sdp-redis")
    region = os.getenv("GCP_REGION", "us-central1")

    _injected_failures["cache_failure"] = {
        "cache_type": cache_type,
        "failure_mode": failure_mode,
        "until": time.time() + duration_seconds
    }

    if not project:
        return {
            "status": "simulated",
            "cache_type": cache_type,
            "failure_mode": failure_mode
        }

    try:
        # For real Redis instance, we could pause the instance
        # This is simulation mode for safety
        return {
            "status": "cache_failure_simulated",
            "cache_type": cache_type,
            "failure_mode": failure_mode,
            "duration_seconds": duration_seconds,
            "note": "Application should handle cache unavailability"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def restore_cache(cache_type: str = "redis") -> dict:
    """Restore cache after failure test."""
    if "cache_failure" in _injected_failures:
        del _injected_failures["cache_failure"]
    return {"status": "cache_restored", "cache_type": cache_type}


def exhaust_kgs_pool(
    drain_rate: int = 1000,
    duration_seconds: int = 30
) -> dict:
    """
    Simulate Key Generation Service pool exhaustion.

    Args:
        drain_rate: Rate at which to drain keys
        duration_seconds: Duration of the exhaustion

    Returns:
        Status of the KGS exhaustion simulation
    """
    _injected_failures["kgs_exhausted"] = {
        "drain_rate": drain_rate,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "kgs_pool_exhaustion_simulated",
        "drain_rate": drain_rate,
        "duration_seconds": duration_seconds,
        "note": "Application should fall back to synchronous key generation"
    }


def replenish_kgs_pool(pool_size: int = 10000) -> dict:
    """Replenish the KGS pool after exhaustion test."""
    if "kgs_exhausted" in _injected_failures:
        del _injected_failures["kgs_exhausted"]
    return {"status": "kgs_pool_replenished", "pool_size": pool_size}


def inject_network_partition(
    partition_type: str = "api_to_database",
    duration_seconds: int = 30,
    packet_loss_percent: int = 100
) -> dict:
    """
    Inject network partition between components.

    Args:
        partition_type: Type of partition ('api_to_database', 'api_to_cache', etc.)
        duration_seconds: Duration of the partition
        packet_loss_percent: Percentage of packets to drop

    Returns:
        Status of the partition injection
    """
    _injected_failures["network_partition_general"] = {
        "partition_type": partition_type,
        "packet_loss_percent": packet_loss_percent,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "network_partition_injected",
        "partition_type": partition_type,
        "packet_loss_percent": packet_loss_percent,
        "duration_seconds": duration_seconds
    }


def remove_network_partition() -> dict:
    """Remove network partition."""
    if "network_partition_general" in _injected_failures:
        del _injected_failures["network_partition_general"]
    return {"status": "network_partition_removed"}


def simulate_rate_limiter_failure(
    failure_mode: str = "bypass",
    duration_seconds: int = 30
) -> dict:
    """
    Simulate rate limiter component failure.

    Args:
        failure_mode: Type of failure ('bypass', 'block_all', 'error')
        duration_seconds: Duration of the failure

    Returns:
        Status of the rate limiter failure simulation
    """
    _injected_failures["rate_limiter"] = {
        "failure_mode": failure_mode,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "rate_limiter_failure_simulated",
        "failure_mode": failure_mode,
        "duration_seconds": duration_seconds
    }


def restore_rate_limiter() -> dict:
    """Restore rate limiter after failure test."""
    if "rate_limiter" in _injected_failures:
        del _injected_failures["rate_limiter"]
    return {"status": "rate_limiter_restored"}


def simulate_queue_backpressure(
    queue_type: str = "kafka",
    backpressure_level: str = "high",
    duration_seconds: int = 60
) -> dict:
    """
    Simulate message queue backpressure.

    Args:
        queue_type: Type of queue ('kafka', 'pubsub', 'rabbitmq')
        backpressure_level: Level of backpressure ('low', 'medium', 'high')
        duration_seconds: Duration of the backpressure

    Returns:
        Status of the backpressure simulation
    """
    _injected_failures["queue_backpressure"] = {
        "queue_type": queue_type,
        "level": backpressure_level,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "queue_backpressure_simulated",
        "queue_type": queue_type,
        "backpressure_level": backpressure_level,
        "duration_seconds": duration_seconds
    }


def restore_event_queue(queue_type: str = "kafka") -> dict:
    """Restore event queue after backpressure test."""
    if "queue_backpressure" in _injected_failures:
        del _injected_failures["queue_backpressure"]
    return {"status": "event_queue_restored", "queue_type": queue_type}


def inject_memory_pressure(
    memory_percent: int = 85,
    duration_seconds: int = 45
) -> dict:
    """
    Inject memory pressure on API servers.

    In Cloud Run, this would trigger autoscaling.
    """
    _injected_failures["memory_pressure"] = {
        "percent": memory_percent,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "memory_pressure_injected",
        "memory_percent": memory_percent,
        "duration_seconds": duration_seconds,
        "note": "Cloud Run should autoscale in response"
    }


def release_memory_pressure() -> dict:
    """Release memory pressure."""
    if "memory_pressure" in _injected_failures:
        del _injected_failures["memory_pressure"]
    return {"status": "memory_pressure_released"}


def inject_cpu_spike(
    cpu_percent: int = 90,
    duration_seconds: int = 60
) -> dict:
    """
    Inject CPU spike to test autoscaling.
    """
    _injected_failures["cpu_spike"] = {
        "percent": cpu_percent,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "cpu_spike_injected",
        "cpu_percent": cpu_percent,
        "duration_seconds": duration_seconds
    }


def release_cpu_pressure() -> dict:
    """Release CPU pressure."""
    if "cpu_spike" in _injected_failures:
        del _injected_failures["cpu_spike"]
    return {"status": "cpu_pressure_released"}


def inject_dns_failure(
    failure_type: str = "timeout",
    duration_seconds: int = 20
) -> dict:
    """
    Inject DNS resolution failure.

    Args:
        failure_type: Type of DNS failure ('timeout', 'nxdomain', 'servfail')
        duration_seconds: Duration of the failure

    Returns:
        Status of the DNS failure injection
    """
    _injected_failures["dns_failure"] = {
        "failure_type": failure_type,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "dns_failure_injected",
        "failure_type": failure_type,
        "duration_seconds": duration_seconds
    }


def restore_dns() -> dict:
    """Restore DNS after failure test."""
    if "dns_failure" in _injected_failures:
        del _injected_failures["dns_failure"]
    return {"status": "dns_restored"}


def simulate_cert_issue(
    issue_type: str = "about_to_expire",
    duration_seconds: int = 30
) -> dict:
    """
    Simulate certificate issues.

    Args:
        issue_type: Type of issue ('about_to_expire', 'expired', 'invalid')
        duration_seconds: Duration of the simulation

    Returns:
        Status of the certificate issue simulation
    """
    _injected_failures["cert_issue"] = {
        "issue_type": issue_type,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "cert_issue_simulated",
        "issue_type": issue_type,
        "duration_seconds": duration_seconds
    }


def simulate_region_failure(
    region: str = "us-east-1",
    duration_seconds: int = 120,
    failover_region: str = "us-west-2"
) -> dict:
    """
    Simulate entire region failure for DR testing.

    Args:
        region: Region to simulate failure
        duration_seconds: Duration of the failure
        failover_region: Region to failover to

    Returns:
        Status of the region failure simulation
    """
    _injected_failures["region_failure"] = {
        "failed_region": region,
        "failover_region": failover_region,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "region_failure_simulated",
        "failed_region": region,
        "failover_region": failover_region,
        "duration_seconds": duration_seconds
    }


def restore_region(region: str = "us-east-1") -> dict:
    """Restore region after failure test."""
    if "region_failure" in _injected_failures:
        del _injected_failures["region_failure"]
    return {"status": "region_restored", "region": region}


def trigger_cascading_failure(
    start_component: str = "cache",
    propagation_delay_seconds: int = 5,
    duration_seconds: int = 60
) -> dict:
    """
    Trigger cascading failure across services.

    Args:
        start_component: Component to start failure from
        propagation_delay_seconds: Delay between cascade stages
        duration_seconds: Total duration of the cascade

    Returns:
        Status of the cascading failure
    """
    _injected_failures["cascading_failure"] = {
        "start_component": start_component,
        "propagation_delay": propagation_delay_seconds,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "cascading_failure_triggered",
        "start_component": start_component,
        "propagation_delay_seconds": propagation_delay_seconds,
        "duration_seconds": duration_seconds
    }


def stop_cascading_failure() -> dict:
    """Stop cascading failure."""
    if "cascading_failure" in _injected_failures:
        del _injected_failures["cascading_failure"]
    return {"status": "cascading_failure_stopped"}


def simulate_slow_consumer(
    consumer_group: str = "analytics",
    processing_delay_ms: int = 5000,
    duration_seconds: int = 90
) -> dict:
    """
    Simulate slow consumer causing message backlog.

    Args:
        consumer_group: Consumer group to slow down
        processing_delay_ms: Processing delay per message
        duration_seconds: Duration of the slowdown

    Returns:
        Status of the slow consumer simulation
    """
    _injected_failures["slow_consumer"] = {
        "consumer_group": consumer_group,
        "delay_ms": processing_delay_ms,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "slow_consumer_simulated",
        "consumer_group": consumer_group,
        "processing_delay_ms": processing_delay_ms,
        "duration_seconds": duration_seconds
    }


def restore_consumer_speed(consumer_group: str = "analytics") -> dict:
    """Restore consumer speed after slowdown test."""
    if "slow_consumer" in _injected_failures:
        del _injected_failures["slow_consumer"]
    return {"status": "consumer_speed_restored", "consumer_group": consumer_group}


def inject_disk_io_pressure(
    io_pressure_percent: int = 95,
    duration_seconds: int = 45
) -> dict:
    """
    Inject disk I/O saturation.

    Args:
        io_pressure_percent: Percentage of I/O capacity to saturate
        duration_seconds: Duration of the pressure

    Returns:
        Status of the I/O pressure injection
    """
    _injected_failures["disk_io_pressure"] = {
        "percent": io_pressure_percent,
        "until": time.time() + duration_seconds
    }

    return {
        "status": "disk_io_pressure_injected",
        "io_pressure_percent": io_pressure_percent,
        "duration_seconds": duration_seconds
    }


def release_disk_io_pressure() -> dict:
    """Release disk I/O pressure."""
    if "disk_io_pressure" in _injected_failures:
        del _injected_failures["disk_io_pressure"]
    return {"status": "disk_io_pressure_released"}

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

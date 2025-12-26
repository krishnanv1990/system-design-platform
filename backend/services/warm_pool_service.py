"""
Warm Pool Deployment Service.

Architecture:
- Pre-provisioned standard services (Postgres, Cassandra, Kafka, Redis)
- Pool of warm containers ready to accept candidate API code
- Candidate's API is injected and container activated in seconds

Deployment flow:
1. Candidate submits API code
2. Grab warm container from pool
3. Inject candidate's code via ConfigMap/Volume
4. Activate container (already running, just switch to candidate code)
5. Run tests against candidate's API
6. Return container to pool after cleanup
"""

import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

from backend.config import get_settings

settings = get_settings()


class ServiceType(str, Enum):
    """Standard infrastructure services available to candidates."""
    POSTGRES = "postgres"
    CASSANDRA = "cassandra"  # Or ScyllaDB
    KAFKA = "kafka"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    MONGODB = "mongodb"


@dataclass
class InfraService:
    """Pre-provisioned infrastructure service."""
    service_type: ServiceType
    host: str
    port: int
    connection_string: str
    credentials: Dict[str, str] = field(default_factory=dict)


@dataclass
class WarmContainer:
    """A warm container ready to accept candidate code."""
    container_id: str
    status: str  # "available", "in_use", "draining"
    endpoint: str
    created_at: datetime
    last_used: Optional[datetime] = None
    current_submission_id: Optional[int] = None


class WarmPoolService:
    """
    Manages a pool of warm containers for instant deployment.

    Key features:
    - Pre-provisioned infrastructure services
    - Pool of warm API containers
    - Hot-swap candidate code without container restart
    - Sub-second deployment times
    """

    def __init__(self):
        self.pool_size = 10  # Number of warm containers to maintain
        self.warm_containers: List[WarmContainer] = []
        self.infrastructure = self._setup_infrastructure()

    def _setup_infrastructure(self) -> Dict[ServiceType, InfraService]:
        """
        Define pre-provisioned infrastructure services.
        These are always running and shared by all candidates.
        """
        project_id = settings.gcp_project_id
        region = settings.gcp_region

        return {
            ServiceType.POSTGRES: InfraService(
                service_type=ServiceType.POSTGRES,
                host=f"sdp-postgres.{region}.c.{project_id}.internal",
                port=5432,
                connection_string=f"postgresql://sdp_user:${{POSTGRES_PASSWORD}}@sdp-postgres:5432/sdp_db",
                credentials={"username": "sdp_user", "password_secret": "sdp-postgres-password"},
            ),
            ServiceType.CASSANDRA: InfraService(
                service_type=ServiceType.CASSANDRA,
                host=f"sdp-cassandra.{region}.c.{project_id}.internal",
                port=9042,
                connection_string=f"cassandra://sdp-cassandra:9042/sdp_keyspace",
                credentials={"username": "cassandra", "password_secret": "sdp-cassandra-password"},
            ),
            ServiceType.KAFKA: InfraService(
                service_type=ServiceType.KAFKA,
                host=f"sdp-kafka.{region}.c.{project_id}.internal",
                port=9092,
                connection_string=f"sdp-kafka:9092",
                credentials={},
            ),
            ServiceType.REDIS: InfraService(
                service_type=ServiceType.REDIS,
                host=f"sdp-redis.{region}.c.{project_id}.internal",
                port=6379,
                connection_string=f"redis://sdp-redis:6379",
                credentials={"password_secret": "sdp-redis-password"},
            ),
            ServiceType.ELASTICSEARCH: InfraService(
                service_type=ServiceType.ELASTICSEARCH,
                host=f"sdp-elasticsearch.{region}.c.{project_id}.internal",
                port=9200,
                connection_string=f"http://sdp-elasticsearch:9200",
                credentials={"username": "elastic", "password_secret": "sdp-elastic-password"},
            ),
            ServiceType.MONGODB: InfraService(
                service_type=ServiceType.MONGODB,
                host=f"sdp-mongodb.{region}.c.{project_id}.internal",
                port=27017,
                connection_string=f"mongodb://sdp-mongodb:27017/sdp_db",
                credentials={"username": "sdp_user", "password_secret": "sdp-mongodb-password"},
            ),
        }

    async def deploy_candidate_api(
        self,
        submission_id: int,
        api_code: str,
        required_services: List[ServiceType],
        api_spec: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Deploy candidate's API code to a warm container.

        Args:
            submission_id: Unique submission ID
            api_code: Candidate's Python API code (FastAPI)
            required_services: List of infrastructure services needed
            api_spec: Optional API specification

        Returns:
            Deployment result with endpoint URL
        """
        start_time = datetime.utcnow()

        # 1. Get available warm container from pool
        container = await self._acquire_container(submission_id)
        if not container:
            return {
                "success": False,
                "error": "No warm containers available",
            }

        try:
            # 2. Generate namespace for isolation
            namespace = f"sub-{submission_id}"

            # 3. Prepare environment variables for required services
            env_vars = self._prepare_service_connections(required_services, namespace)

            # 4. Inject candidate's code into the container
            await self._inject_code(container, api_code, env_vars)

            # 5. Activate the container with new code
            await self._activate_container(container)

            # 6. Wait for health check
            endpoint_url = await self._wait_for_healthy(container)

            deployment_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                "success": True,
                "submission_id": submission_id,
                "container_id": container.container_id,
                "endpoint_url": endpoint_url,
                "namespace": namespace,
                "deployment_time_seconds": deployment_time,
                "services": {s.value: self.infrastructure[s].host for s in required_services},
            }

        except Exception as e:
            # Return container to pool on failure
            await self._release_container(container)
            return {
                "success": False,
                "error": str(e),
                "deployment_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
            }

    def _prepare_service_connections(
        self,
        required_services: List[ServiceType],
        namespace: str,
    ) -> Dict[str, str]:
        """
        Prepare environment variables for connecting to infrastructure services.
        Each candidate gets isolated namespace within shared services.
        """
        env_vars = {
            "NAMESPACE": namespace,
            "SUBMISSION_ID": namespace.replace("sub-", ""),
        }

        for service_type in required_services:
            service = self.infrastructure[service_type]
            prefix = service_type.value.upper()

            if service_type == ServiceType.POSTGRES:
                # Use schema-based isolation
                env_vars[f"{prefix}_HOST"] = service.host
                env_vars[f"{prefix}_PORT"] = str(service.port)
                env_vars[f"{prefix}_DATABASE"] = "sdp_db"
                env_vars[f"{prefix}_SCHEMA"] = namespace.replace("-", "_")
                env_vars["DATABASE_URL"] = (
                    f"postgresql://{service.credentials['username']}:"
                    f"${{POSTGRES_PASSWORD}}@{service.host}:{service.port}"
                    f"/sdp_db?options=-csearch_path={namespace.replace('-', '_')}"
                )

            elif service_type == ServiceType.CASSANDRA:
                # Use keyspace-based isolation
                env_vars[f"{prefix}_HOST"] = service.host
                env_vars[f"{prefix}_PORT"] = str(service.port)
                env_vars[f"{prefix}_KEYSPACE"] = namespace.replace("-", "_")
                env_vars["CASSANDRA_URL"] = service.connection_string

            elif service_type == ServiceType.KAFKA:
                # Use topic prefix-based isolation
                env_vars[f"{prefix}_BOOTSTRAP_SERVERS"] = f"{service.host}:{service.port}"
                env_vars[f"{prefix}_TOPIC_PREFIX"] = f"{namespace}-"
                env_vars["KAFKA_BROKERS"] = f"{service.host}:{service.port}"

            elif service_type == ServiceType.REDIS:
                # Use key prefix-based isolation
                env_vars[f"{prefix}_HOST"] = service.host
                env_vars[f"{prefix}_PORT"] = str(service.port)
                env_vars[f"{prefix}_KEY_PREFIX"] = f"{namespace}:"
                env_vars["REDIS_URL"] = f"redis://{service.host}:{service.port}"

            elif service_type == ServiceType.MONGODB:
                # Use database-based isolation
                env_vars[f"{prefix}_HOST"] = service.host
                env_vars[f"{prefix}_PORT"] = str(service.port)
                env_vars[f"{prefix}_DATABASE"] = namespace.replace("-", "_")
                env_vars["MONGODB_URL"] = (
                    f"mongodb://{service.host}:{service.port}/{namespace.replace('-', '_')}"
                )

            elif service_type == ServiceType.ELASTICSEARCH:
                # Use index prefix-based isolation
                env_vars[f"{prefix}_HOST"] = service.host
                env_vars[f"{prefix}_PORT"] = str(service.port)
                env_vars[f"{prefix}_INDEX_PREFIX"] = f"{namespace}-"
                env_vars["ELASTICSEARCH_URL"] = f"http://{service.host}:{service.port}"

        return env_vars

    async def _acquire_container(self, submission_id: int) -> Optional[WarmContainer]:
        """Acquire an available container from the warm pool."""
        for container in self.warm_containers:
            if container.status == "available":
                container.status = "in_use"
                container.current_submission_id = submission_id
                container.last_used = datetime.utcnow()
                return container

        # If no containers available, try to create one
        return await self._create_warm_container()

    async def _release_container(self, container: WarmContainer) -> None:
        """Release a container back to the warm pool after cleanup."""
        # Clean up candidate code and data
        await self._cleanup_container(container)

        # Mark as available
        container.status = "available"
        container.current_submission_id = None

    async def _inject_code(
        self,
        container: WarmContainer,
        api_code: str,
        env_vars: Dict[str, str],
    ) -> None:
        """
        Inject candidate's API code into a warm container.

        Uses Kubernetes ConfigMap or Cloud Run volume to hot-swap code.
        """
        # In Kubernetes: Update ConfigMap and trigger volume refresh
        # In Cloud Run: Update with new revision (still fast due to warm instance)

        # For now, simulate the injection
        # In production, this would use kubectl or gcloud commands
        pass

    async def _activate_container(self, container: WarmContainer) -> None:
        """Activate the container with the new candidate code."""
        # Send signal to container to reload code
        # Container is already running, just needs to load new code
        pass

    async def _wait_for_healthy(self, container: WarmContainer, timeout: int = 10) -> str:
        """Wait for the container to become healthy and return endpoint."""
        # Poll health endpoint
        for _ in range(timeout * 2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{container.endpoint}/health", timeout=1) as resp:
                        if resp.status == 200:
                            return container.endpoint
            except Exception:
                pass
            await asyncio.sleep(0.5)

        raise Exception("Container failed health check")

    async def _cleanup_container(self, container: WarmContainer) -> None:
        """Clean up a container for reuse."""
        # Clear candidate code
        # Reset any state
        # Clear namespace-specific data from services
        pass

    async def _create_warm_container(self) -> Optional[WarmContainer]:
        """Create a new warm container if pool is exhausted."""
        container_id = f"warm-{uuid.uuid4().hex[:8]}"

        # In production, this would:
        # 1. Deploy a new container from the warm image
        # 2. Wait for it to be ready
        # 3. Add to pool

        container = WarmContainer(
            container_id=container_id,
            status="available",
            endpoint=f"https://{container_id}.run.app",
            created_at=datetime.utcnow(),
        )
        self.warm_containers.append(container)
        return container

    async def cleanup_submission(self, submission_id: int) -> Dict[str, Any]:
        """Clean up all resources for a submission."""
        namespace = f"sub-{submission_id}"

        # Find the container
        container = None
        for c in self.warm_containers:
            if c.current_submission_id == submission_id:
                container = c
                break

        if container:
            await self._release_container(container)

        # Clean up namespace data from all services
        cleanup_results = {
            "namespace": namespace,
            "cleaned_services": [],
        }

        # Postgres: Drop schema
        # Cassandra: Drop keyspace (or truncate tables)
        # Kafka: Delete topics with prefix
        # Redis: Delete keys with prefix
        # MongoDB: Drop database
        # Elasticsearch: Delete indices with prefix

        return cleanup_results

    def get_pool_status(self) -> Dict[str, Any]:
        """Get current status of the warm pool."""
        return {
            "total_containers": len(self.warm_containers),
            "available": sum(1 for c in self.warm_containers if c.status == "available"),
            "in_use": sum(1 for c in self.warm_containers if c.status == "in_use"),
            "draining": sum(1 for c in self.warm_containers if c.status == "draining"),
            "containers": [
                {
                    "id": c.container_id,
                    "status": c.status,
                    "submission_id": c.current_submission_id,
                    "created_at": c.created_at.isoformat(),
                }
                for c in self.warm_containers
            ],
        }


# Kubernetes manifests for warm pool infrastructure
WARM_POOL_K8S_MANIFESTS = """
# Pre-provisioned Infrastructure Services
---
apiVersion: v1
kind: Namespace
metadata:
  name: sdp-infra

---
# PostgreSQL StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: sdp-postgres
  namespace: sdp-infra
spec:
  serviceName: sdp-postgres
  replicas: 1
  selector:
    matchLabels:
      app: sdp-postgres
  template:
    metadata:
      labels:
        app: sdp-postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: sdp_db
        - name: POSTGRES_USER
          value: sdp_user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sdp-secrets
              key: postgres-password
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi

---
# ScyllaDB (Cassandra-compatible) StatefulSet
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: sdp-cassandra
  namespace: sdp-infra
spec:
  serviceName: sdp-cassandra
  replicas: 3
  selector:
    matchLabels:
      app: sdp-cassandra
  template:
    metadata:
      labels:
        app: sdp-cassandra
    spec:
      containers:
      - name: scylla
        image: scylladb/scylla:5.2
        ports:
        - containerPort: 9042
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
        volumeMounts:
        - name: data
          mountPath: /var/lib/scylla
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 50Gi

---
# Kafka (using Strimzi operator)
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: sdp-kafka
  namespace: sdp-infra
spec:
  kafka:
    replicas: 3
    listeners:
    - name: plain
      port: 9092
      type: internal
      tls: false
    storage:
      type: persistent-claim
      size: 20Gi
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 5Gi

---
# Redis Cluster
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: sdp-redis
  namespace: sdp-infra
spec:
  serviceName: sdp-redis
  replicas: 3
  selector:
    matchLabels:
      app: sdp-redis
  template:
    metadata:
      labels:
        app: sdp-redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 5Gi

---
# Warm Container Pool Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sdp-warm-pool
  namespace: sdp-candidates
spec:
  replicas: 10  # Pool size
  selector:
    matchLabels:
      app: sdp-warm-container
  template:
    metadata:
      labels:
        app: sdp-warm-container
    spec:
      containers:
      - name: api
        image: gcr.io/PROJECT_ID/sdp-warm-base:latest
        ports:
        - containerPort: 8080
        env:
        - name: MODE
          value: "warm"  # Waiting for code injection
        volumeMounts:
        - name: candidate-code
          mountPath: /app/candidate
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 1
          periodSeconds: 2
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: candidate-code
        emptyDir: {}  # Will be populated via ConfigMap
"""

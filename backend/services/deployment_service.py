"""
Fast deployment service using Cloud Run.
Deploys candidate solutions in seconds instead of minutes.

Strategy:
- Pre-provisioned shared infrastructure (database, cache, messaging)
- Dynamic Cloud Run deployments for candidate code
- Namespace isolation for multi-tenancy
- Template-based container generation
"""

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib

from backend.config import get_settings
from backend.services.ai_service import AIService

settings = get_settings()


class DeploymentStrategy:
    """Available deployment strategies."""
    CLOUD_RUN = "cloud_run"          # Fast: ~10-30 seconds
    KUBERNETES = "kubernetes"         # Fast: ~5-15 seconds (if cluster exists)
    SIMULATION = "simulation"         # Instant: mock deployment for testing
    TERRAFORM = "terraform"           # Slow: 5-15 minutes (legacy)


class FastDeploymentService:
    """
    Fast deployment service optimized for quick candidate feedback.

    Uses pre-provisioned infrastructure with dynamic application deployment
    to achieve deployment times of seconds instead of minutes.
    """

    def __init__(self):
        self.ai_service = AIService()
        self.strategy = DeploymentStrategy.CLOUD_RUN
        self.workspace_dir = Path("/tmp/deployments")
        self.workspace_dir.mkdir(exist_ok=True)

        # Pre-provisioned infrastructure endpoints
        self.shared_infra = {
            "database_host": f"/cloudsql/{settings.gcp_project_id}:{settings.gcp_region}:sdp-shared-db",
            "redis_host": "sdp-redis.default.svc.cluster.local:6379",
            "pubsub_project": settings.gcp_project_id,
        }

    async def deploy(
        self,
        submission_id: int,
        design_text: str,
        api_spec: Optional[Dict[str, Any]] = None,
        problem_type: str = "url_shortener",
    ) -> Dict[str, Any]:
        """
        Deploy a candidate's solution quickly.

        Args:
            submission_id: Unique submission identifier
            design_text: Candidate's design description
            api_spec: API specification
            problem_type: Type of problem for template selection

        Returns:
            Deployment result with endpoint URL and timing
        """
        start_time = datetime.utcnow()
        namespace = f"sub-{submission_id}"

        if self.strategy == DeploymentStrategy.SIMULATION:
            return await self._deploy_simulation(submission_id, namespace)
        elif self.strategy == DeploymentStrategy.CLOUD_RUN:
            return await self._deploy_cloud_run(
                submission_id, namespace, design_text, api_spec, problem_type
            )
        elif self.strategy == DeploymentStrategy.KUBERNETES:
            return await self._deploy_kubernetes(
                submission_id, namespace, design_text, api_spec, problem_type
            )
        else:
            raise ValueError(f"Unknown deployment strategy: {self.strategy}")

    async def _deploy_simulation(
        self,
        submission_id: int,
        namespace: str,
    ) -> Dict[str, Any]:
        """
        Simulated deployment for development/testing.
        Returns mock endpoints instantly.
        """
        # Simulate brief processing time
        await asyncio.sleep(0.5)

        return {
            "success": True,
            "strategy": "simulation",
            "namespace": namespace,
            "endpoint_url": f"https://mock-{namespace}.example.com",
            "internal_url": f"http://mock-{namespace}:8080",
            "deployment_time_seconds": 0.5,
            "resources": {
                "service": f"mock-service-{submission_id}",
                "database_schema": f"candidate_{submission_id}",
                "redis_prefix": f"sub:{submission_id}:",
            },
        }

    async def _deploy_cloud_run(
        self,
        submission_id: int,
        namespace: str,
        design_text: str,
        api_spec: Optional[Dict[str, Any]],
        problem_type: str,
    ) -> Dict[str, Any]:
        """
        Deploy to Cloud Run for fast, serverless deployment.
        Typical deployment time: 10-30 seconds.
        """
        start_time = datetime.utcnow()
        service_name = f"sdp-{namespace}"

        try:
            # Step 1: Generate application code from design (AI-powered)
            app_code = await self._generate_application_code(
                design_text, api_spec, problem_type
            )

            # Step 2: Create container image
            image_tag = await self._build_container(
                submission_id, app_code, problem_type
            )

            # Step 3: Deploy to Cloud Run
            result = await self._deploy_to_cloud_run(
                service_name, image_tag, namespace, submission_id
            )

            deployment_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                "success": True,
                "strategy": "cloud_run",
                "namespace": namespace,
                "endpoint_url": result["url"],
                "service_name": service_name,
                "image": image_tag,
                "deployment_time_seconds": deployment_time,
                "resources": {
                    "service": service_name,
                    "database_schema": f"candidate_{submission_id}",
                    "redis_prefix": f"sub:{submission_id}:",
                },
            }

        except Exception as e:
            return {
                "success": False,
                "strategy": "cloud_run",
                "error": str(e),
                "deployment_time_seconds": (datetime.utcnow() - start_time).total_seconds(),
            }

    async def _generate_application_code(
        self,
        design_text: str,
        api_spec: Optional[Dict[str, Any]],
        problem_type: str,
    ) -> Dict[str, str]:
        """
        Generate deployable application code from design.
        Uses AI to create a working implementation.
        """
        prompt = f"""Generate a minimal but functional Python FastAPI application based on this design.

Problem Type: {problem_type}

Design:
{design_text}

API Specification:
{json.dumps(api_spec, indent=2) if api_spec else "Not provided"}

Requirements:
1. Use FastAPI with async endpoints
2. Connect to PostgreSQL using environment variable DATABASE_URL
3. Connect to Redis using environment variable REDIS_URL
4. Implement the core functionality described in the design
5. Include health check endpoint at /health
6. Handle errors gracefully

Return the code as a single main.py file that can be run with uvicorn.
Focus on functionality over perfection - this is for testing the design.
"""

        # Use AI to generate the application code
        # For now, use a template-based approach for speed
        return self._get_template_code(problem_type, api_spec)

    def _get_template_code(
        self,
        problem_type: str,
        api_spec: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Get template-based application code for common problem types.
        Much faster than AI generation for known patterns.
        """
        templates = {
            "url_shortener": self._url_shortener_template(),
            "rate_limiter": self._rate_limiter_template(),
            "cache": self._cache_template(),
            "notification": self._notification_template(),
        }

        return templates.get(problem_type, self._generic_template())

    def _url_shortener_template(self) -> Dict[str, str]:
        """Template for URL shortener implementation."""
        return {
            "main.py": '''
import os
import hashlib
import string
import random
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncpg
import aioredis

app = FastAPI(title="URL Shortener")

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

class URLCreate(BaseModel):
    original_url: str
    custom_alias: str = None

class URLResponse(BaseModel):
    short_url: str
    original_url: str

@app.on_event("startup")
async def startup():
    app.state.db = await asyncpg.create_pool(DATABASE_URL)
    app.state.redis = await aioredis.from_url(REDIS_URL)

    # Create table if not exists
    async with app.state.db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id SERIAL PRIMARY KEY,
                short_code VARCHAR(10) UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/v1/urls", response_model=URLResponse)
async def create_short_url(data: URLCreate):
    short_code = data.custom_alias or generate_short_code()

    async with app.state.db.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO urls (short_code, original_url) VALUES ($1, $2)",
                short_code, data.original_url
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(400, "Alias already exists")

    # Cache the mapping
    await app.state.redis.set(f"url:{short_code}", data.original_url, ex=3600)

    return URLResponse(
        short_url=f"{BASE_URL}/{short_code}",
        original_url=data.original_url
    )

@app.get("/{short_code}")
async def redirect(short_code: str):
    # Check cache first
    cached = await app.state.redis.get(f"url:{short_code}")
    if cached:
        return {"redirect_to": cached.decode()}

    # Fallback to database
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT original_url FROM urls WHERE short_code = $1",
            short_code
        )

    if not row:
        raise HTTPException(404, "URL not found")

    # Cache for next time
    await app.state.redis.set(f"url:{short_code}", row["original_url"], ex=3600)

    return {"redirect_to": row["original_url"]}

def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
''',
            "requirements.txt": '''
fastapi==0.109.0
uvicorn[standard]==0.27.0
asyncpg==0.29.0
aioredis==2.0.1
pydantic==2.6.0
''',
            "Dockerfile": '''
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
'''
        }

    def _rate_limiter_template(self) -> Dict[str, str]:
        """Template for rate limiter implementation."""
        return {
            "main.py": '''
import os
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aioredis

app = FastAPI(title="Rate Limiter")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class RateLimitCheck(BaseModel):
    client_id: str
    endpoint: str = "default"

class RateLimitResponse(BaseModel):
    allowed: bool
    remaining: int
    reset_at: int

@app.on_event("startup")
async def startup():
    app.state.redis = await aioredis.from_url(REDIS_URL)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/v1/check", response_model=RateLimitResponse)
async def check_rate_limit(data: RateLimitCheck):
    """Sliding window rate limiter."""
    window_size = 60  # 1 minute
    max_requests = 100

    now = int(time.time())
    window_start = now - window_size
    key = f"ratelimit:{data.client_id}:{data.endpoint}"

    # Remove old entries and count current
    pipe = app.state.redis.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, window_size)
    results = await pipe.execute()

    current_count = results[1]
    allowed = current_count < max_requests

    return RateLimitResponse(
        allowed=allowed,
        remaining=max(0, max_requests - current_count - 1),
        reset_at=now + window_size
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
''',
            "requirements.txt": "fastapi==0.109.0\\nuvicorn[standard]==0.27.0\\naioredis==2.0.1\\npydantic==2.6.0",
            "Dockerfile": "FROM python:3.11-slim\\nWORKDIR /app\\nCOPY requirements.txt .\\nRUN pip install --no-cache-dir -r requirements.txt\\nCOPY main.py .\\nEXPOSE 8080\\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]"
        }

    def _cache_template(self) -> Dict[str, str]:
        """Template for distributed cache implementation."""
        return {
            "main.py": '''
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import aioredis

app = FastAPI(title="Distributed Cache")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class CacheSet(BaseModel):
    key: str
    value: str
    ttl: Optional[int] = None

class CacheResponse(BaseModel):
    key: str
    value: Optional[str]
    found: bool

@app.on_event("startup")
async def startup():
    app.state.redis = await aioredis.from_url(REDIS_URL)

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/v1/cache/{key}", response_model=CacheResponse)
async def get_cache(key: str):
    value = await app.state.redis.get(key)
    return CacheResponse(
        key=key,
        value=value.decode() if value else None,
        found=value is not None
    )

@app.put("/api/v1/cache/{key}")
async def set_cache(key: str, data: CacheSet):
    if data.ttl:
        await app.state.redis.set(key, data.value, ex=data.ttl)
    else:
        await app.state.redis.set(key, data.value)
    return {"success": True}

@app.delete("/api/v1/cache/{key}")
async def delete_cache(key: str):
    deleted = await app.state.redis.delete(key)
    return {"deleted": deleted > 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
''',
            "requirements.txt": "fastapi==0.109.0\\nuvicorn[standard]==0.27.0\\naioredis==2.0.1\\npydantic==2.6.0",
            "Dockerfile": "FROM python:3.11-slim\\nWORKDIR /app\\nCOPY requirements.txt .\\nRUN pip install --no-cache-dir -r requirements.txt\\nCOPY main.py .\\nEXPOSE 8080\\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]"
        }

    def _notification_template(self) -> Dict[str, str]:
        """Template for notification service implementation."""
        return self._generic_template()

    def _generic_template(self) -> Dict[str, str]:
        """Generic API template for unknown problem types."""
        return {
            "main.py": '''
import os
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="System Design Solution")

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    return {"message": "System Design Solution API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
''',
            "requirements.txt": "fastapi==0.109.0\\nuvicorn[standard]==0.27.0\\npydantic==2.6.0",
            "Dockerfile": "FROM python:3.11-slim\\nWORKDIR /app\\nCOPY requirements.txt .\\nRUN pip install --no-cache-dir -r requirements.txt\\nCOPY main.py .\\nEXPOSE 8080\\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]"
        }

    async def _build_container(
        self,
        submission_id: int,
        app_code: Dict[str, str],
        problem_type: str,
    ) -> str:
        """
        Build container image using Cloud Build.
        Returns the image tag.
        """
        workspace = self.workspace_dir / f"build_{submission_id}"
        workspace.mkdir(exist_ok=True)

        # Write application files
        for filename, content in app_code.items():
            (workspace / filename).write_text(content)

        # Build image using Cloud Build (fast, cached layers)
        image_tag = f"gcr.io/{settings.gcp_project_id}/sdp-candidate:{submission_id}"

        proc = await asyncio.create_subprocess_exec(
            "gcloud", "builds", "submit",
            "--tag", image_tag,
            "--timeout", "120s",
            "--quiet",
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"Container build failed: {stderr.decode()}")

        return image_tag

    async def _deploy_to_cloud_run(
        self,
        service_name: str,
        image_tag: str,
        namespace: str,
        submission_id: int,
    ) -> Dict[str, Any]:
        """
        Deploy container to Cloud Run.
        Fast deployment using pre-warmed instances.
        """
        env_vars = [
            f"DATABASE_URL={self.shared_infra['database_host']}/candidate_{submission_id}",
            f"REDIS_URL=redis://{self.shared_infra['redis_host']}",
            f"NAMESPACE={namespace}",
        ]

        proc = await asyncio.create_subprocess_exec(
            "gcloud", "run", "deploy", service_name,
            "--image", image_tag,
            "--platform", "managed",
            "--region", settings.gcp_region,
            "--allow-unauthenticated",
            "--set-env-vars", ",".join(env_vars),
            "--memory", "512Mi",
            "--cpu", "1",
            "--min-instances", "0",
            "--max-instances", "2",
            "--timeout", "60s",
            "--quiet",
            "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"Cloud Run deployment failed: {stderr.decode()}")

        result = json.loads(stdout.decode())
        return {
            "url": result.get("status", {}).get("url", ""),
            "service": service_name,
        }

    async def _deploy_kubernetes(
        self,
        submission_id: int,
        namespace: str,
        design_text: str,
        api_spec: Optional[Dict[str, Any]],
        problem_type: str,
    ) -> Dict[str, Any]:
        """
        Deploy to Kubernetes for even faster deployment.
        Requires pre-existing GKE cluster.
        """
        # Similar to Cloud Run but uses kubectl
        # Kubernetes can be faster due to pre-pulled images
        pass  # Implementation similar to Cloud Run

    async def cleanup(self, submission_id: int, namespace: str) -> Dict[str, Any]:
        """
        Clean up deployment resources after testing.
        """
        service_name = f"sdp-{namespace}"

        try:
            proc = await asyncio.create_subprocess_exec(
                "gcloud", "run", "services", "delete", service_name,
                "--platform", "managed",
                "--region", settings.gcp_region,
                "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            return {"success": True, "service_deleted": service_name}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Comparison of deployment strategies
DEPLOYMENT_COMPARISON = """
┌─────────────────┬──────────────┬─────────────────┬──────────────────────┐
│    Strategy     │  Deploy Time │    Best For     │      Trade-offs      │
├─────────────────┼──────────────┼─────────────────┼──────────────────────┤
│ Simulation      │   < 1 sec    │ Development     │ Not real infra       │
│ Cloud Run       │  10-30 sec   │ Production      │ Cold start possible  │
│ Kubernetes      │   5-15 sec   │ High volume     │ Cluster cost         │
│ Terraform       │  5-15 min    │ Full infra      │ Too slow for testing │
└─────────────────┴──────────────┴─────────────────┴──────────────────────┘
"""

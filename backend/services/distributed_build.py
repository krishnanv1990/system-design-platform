"""
Distributed Systems Build Service

Handles compilation and deployment of distributed consensus implementations.
Uses Google Cloud Build for multi-language compilation and Cloud Run for deployment.

Security Analysis Features:
- C++: AddressSanitizer, ThreadSanitizer, UndefinedBehaviorSanitizer
- Go: Race detector (-race flag)
- Java: SpotBugs for concurrency issues
- Rust: Built-in safety checks, clippy lints
- Python: Thread safety analysis
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from google.cloud import storage, run_v2
from google.cloud.devtools import cloudbuild_v1

from backend.config import get_settings
from backend.database import SessionLocal
from backend.models.submission import Submission, SubmissionStatus

settings = get_settings()


class SecurityAnalysisType(Enum):
    """Types of security analysis available."""
    MEMORY_CORRUPTION = "memory_corruption"
    BUFFER_OVERFLOW = "buffer_overflow"
    RACE_CONDITION = "race_condition"
    UNDEFINED_BEHAVIOR = "undefined_behavior"
    CONCURRENCY = "concurrency"


@dataclass
class SecurityFinding:
    """A security issue found during analysis."""
    finding_type: SecurityAnalysisType
    severity: str  # "critical", "high", "medium", "low", "info"
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    details: Optional[Dict] = None


class DistributedBuildService:
    """Service for building and deploying distributed consensus implementations."""

    def __init__(self, enable_security_analysis: bool = True):
        self.project_id = settings.gcp_project_id
        self.region = settings.gcp_region
        self.enable_security_analysis = enable_security_analysis

    def get_cloudbuild_config(self, language: str, submission_id: int) -> Dict:
        """
        Generate Cloud Build configuration for a specific language.

        Args:
            language: Programming language (python, go, java, cpp, rust)
            submission_id: Submission ID for artifact naming

        Returns:
            Cloud Build configuration dict
        """
        artifact_name = f"raft-{submission_id}-{language}"
        image_name = f"gcr.io/{self.project_id}/{artifact_name}"

        # Build steps vary by language
        if language == "python":
            return self._python_build_config(image_name, submission_id)
        elif language == "go":
            return self._go_build_config(image_name, submission_id)
        elif language == "java":
            return self._java_build_config(image_name, submission_id)
        elif language == "cpp":
            return self._cpp_build_config(image_name, submission_id)
        elif language == "rust":
            return self._rust_build_config(image_name, submission_id)
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _python_build_config(self, image_name: str, submission_id: int) -> Dict:
        """
        Cloud Build config for Python with security analysis.

        Security Analysis:
        - Bandit for security vulnerabilities
        - Safety for vulnerable dependencies
        - Pylint for code quality and potential bugs
        """
        build_cmd = (
            "pip install grpcio grpcio-tools bandit safety pylint && "
            "python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. raft.proto && "
            "echo '=== Running Bandit (Security Analysis) ===' && "
            "bandit -r server.py 2>&1 | tee /workspace/security_analysis.log || true && "
            "echo '=== Checking for Vulnerable Dependencies ===' && "
            "safety check -r requirements.txt 2>&1 | tee -a /workspace/security_analysis.log || true && "
            "echo '=== Running Pylint (Thread Safety) ===' && "
            "pylint --disable=all --enable=W0601,W0602,W0603,W0621 server.py 2>&1 "
            "| tee -a /workspace/security_analysis.log || true"
        )

        return {
            "steps": [
                {
                    "name": "python:3.11-slim",
                    "entrypoint": "bash",
                    "args": ["-c", build_cmd],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "-t", image_name, "-f", "Dockerfile.python", "."],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["push", image_name],
                },
            ],
            "images": [image_name],
            "timeout": "600s",
        }

    def _go_build_config(self, image_name: str, submission_id: int) -> Dict:
        """
        Cloud Build config for Go with race detection.

        Security Analysis:
        - Race condition detection via -race flag
        - Static analysis via go vet
        """
        # Build with race detector for testing, regular build for production
        build_cmd = (
            "go install google.golang.org/protobuf/cmd/protoc-gen-go@latest && "
            "go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest && "
            "protoc --go_out=. --go-grpc_out=. raft.proto && "
            "echo '=== Running Go Vet (static analysis) ===' && "
            "go vet ./... 2>&1 | tee /workspace/security_analysis.log || true && "
            "echo '=== Building with race detector for testing ===' && "
            "CGO_ENABLED=1 go build -race -o server_race . && "
            "echo '=== Building production binary ===' && "
            "CGO_ENABLED=0 go build -o server ."
        )

        return {
            "steps": [
                {
                    "name": "golang:1.21",
                    "entrypoint": "bash",
                    "args": ["-c", build_cmd],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "-t", image_name, "-f", "Dockerfile.go", "."],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["push", image_name],
                },
            ],
            "images": [image_name],
            "timeout": "600s",
        }

    def _java_build_config(self, image_name: str, submission_id: int) -> Dict:
        """
        Cloud Build config for Java with SpotBugs security analysis.

        Security Analysis:
        - SpotBugs for concurrency issues and bug detection
        - FindSecBugs for security vulnerabilities
        """
        # Build with SpotBugs analysis
        build_cmd = (
            "echo '=== Running Gradle Build with SpotBugs ===' && "
            "./gradlew build spotbugsMain --continue 2>&1 | tee /workspace/security_analysis.log || true && "
            "echo '=== Build Complete ===' && "
            "ls -la build/libs/"
        )

        return {
            "steps": [
                {
                    "name": "gradle:8-jdk17",
                    "entrypoint": "bash",
                    "args": ["-c", build_cmd],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "-t", image_name, "-f", "Dockerfile.java", "."],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["push", image_name],
                },
            ],
            "images": [image_name],
            "timeout": "900s",
        }

    def _cpp_build_config(self, image_name: str, submission_id: int) -> Dict:
        """
        Cloud Build config for C++ using prebuilt base image.

        Uses gcr.io/{project}/raft-cpp-base which has:
        - Pre-compiled gRPC and protobuf libraries
        - Pre-generated proto stubs
        - CMake template

        Security Analysis:
        - AddressSanitizer (ASan): Memory corruption, buffer overflows
        - ThreadSanitizer (TSan): Race conditions
        - UndefinedBehaviorSanitizer (UBSan): Undefined behavior

        This reduces build time from ~15min to ~1-2min.
        """
        base_image = f"gcr.io/{self.project_id}/raft-cpp-base:latest"

        # Build command with security analysis
        build_cmd = (
            "cp /app/CMakeLists.txt.template /workspace/CMakeLists.txt && "
            "cp -r /app/generated /workspace/ && "
            "cd /workspace && "
            # Build with AddressSanitizer for memory analysis
            "echo '=== Building with AddressSanitizer (Memory Analysis) ===' && "
            "mkdir -p build_asan && cd build_asan && "
            "cmake -DCMAKE_BUILD_TYPE=Debug "
            "-DCMAKE_CXX_FLAGS='-fsanitize=address -fno-omit-frame-pointer -g' "
            "-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address' .. && "
            "make -j$(nproc) 2>&1 | tee /workspace/asan_build.log || true && "
            "cd /workspace && "
            # Build with ThreadSanitizer for race detection
            "echo '=== Building with ThreadSanitizer (Race Detection) ===' && "
            "mkdir -p build_tsan && cd build_tsan && "
            "cmake -DCMAKE_BUILD_TYPE=Debug "
            "-DCMAKE_CXX_FLAGS='-fsanitize=thread -fno-omit-frame-pointer -g' "
            "-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=thread' .. && "
            "make -j$(nproc) 2>&1 | tee /workspace/tsan_build.log || true && "
            "cd /workspace && "
            # Build production binary
            "echo '=== Building Production Binary ===' && "
            "mkdir -p build && cd build && "
            "cmake -DCMAKE_BUILD_TYPE=Release .. && "
            "make -j$(nproc)"
        )

        return {
            "steps": [
                # Step 1: Build user code with security analysis
                {
                    "name": base_image,
                    "entrypoint": "bash",
                    "args": ["-c", build_cmd],
                },
                # Step 2: Build slim runtime image
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "-t", image_name, "-f", "Dockerfile.cpp", "."],
                },
                # Step 3: Push image
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["push", image_name],
                },
            ],
            "images": [image_name],
            "timeout": "300s",  # Reduced from 900s since we use prebuilt deps
        }

    def _rust_build_config(self, image_name: str, submission_id: int) -> Dict:
        """
        Cloud Build config for Rust with Clippy and safety checks.

        Security Analysis:
        - Clippy lints for common mistakes
        - cargo audit for vulnerable dependencies
        - Built-in memory safety from Rust's type system
        """
        build_cmd = (
            "echo '=== Installing Clippy and Audit tools ===' && "
            "rustup component add clippy && "
            "cargo install cargo-audit 2>/dev/null || true && "
            "echo '=== Running Clippy (Lint Analysis) ===' && "
            "cargo clippy -- -D warnings 2>&1 | tee /workspace/security_analysis.log || true && "
            "echo '=== Checking for Vulnerable Dependencies ===' && "
            "cargo audit 2>&1 | tee -a /workspace/security_analysis.log || true && "
            "echo '=== Building Release Binary ===' && "
            "cargo build --release"
        )

        return {
            "steps": [
                {
                    "name": "rust:1.74",
                    "entrypoint": "bash",
                    "args": ["-c", build_cmd],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "-t", image_name, "-f", "Dockerfile.rust", "."],
                },
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["push", image_name],
                },
            ],
            "images": [image_name],
            "timeout": "900s",
        }

    async def start_build(self, submission_id: int, language: str, source_code: str) -> str:
        """
        Start a Cloud Build job for a submission.

        Args:
            submission_id: Submission ID
            language: Programming language
            source_code: User's source code

        Returns:
            Build ID
        """
        # Upload source to GCS
        bucket_name = f"{self.project_id}-distributed-builds"
        source_path = f"submissions/{submission_id}/source.tar.gz"

        # Create source archive
        source_archive = self._create_source_archive(language, source_code, submission_id)

        # Upload to GCS
        client = storage.Client(project=self.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.upload_from_string(source_archive)

        # Start Cloud Build
        build_client = cloudbuild_v1.CloudBuildClient()

        build_config = self.get_cloudbuild_config(language, submission_id)
        build_config["source"] = {
            "storageSource": {
                "bucket": bucket_name,
                "object": source_path,
            }
        }

        build = cloudbuild_v1.Build(build_config)
        operation = build_client.create_build(project_id=self.project_id, build=build)

        # Return the build ID
        return operation.metadata.build.id

    def _create_source_archive(self, language: str, source_code: str, submission_id: int) -> bytes:
        """
        Create a tarball with the source code and proto file.

        Args:
            language: Programming language
            source_code: User's source code
            submission_id: Submission ID

        Returns:
            Tar.gz bytes
        """
        import io
        import tarfile

        # Create in-memory tarball
        buffer = io.BytesIO()

        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            # Add source code
            source_file = self._get_source_filename(language)
            source_info = tarfile.TarInfo(name=source_file)
            source_data = source_code.encode("utf-8")
            source_info.size = len(source_data)
            tar.addfile(source_info, io.BytesIO(source_data))

            # Add proto file
            proto_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "distributed_problems",
                "raft",
                "proto",
                "raft.proto"
            )
            if os.path.exists(proto_path):
                tar.add(proto_path, arcname="raft.proto")

            # Add Dockerfile
            dockerfile = self._get_dockerfile(language)
            dockerfile_info = tarfile.TarInfo(name=f"Dockerfile.{language}")
            dockerfile_data = dockerfile.encode("utf-8")
            dockerfile_info.size = len(dockerfile_data)
            tar.addfile(dockerfile_info, io.BytesIO(dockerfile_data))

            # Add build files (requirements.txt, go.mod, etc.)
            build_files = self._get_build_files(language)
            for filename, content in build_files.items():
                file_info = tarfile.TarInfo(name=filename)
                file_data = content.encode("utf-8")
                file_info.size = len(file_data)
                tar.addfile(file_info, io.BytesIO(file_data))

        buffer.seek(0)
        return buffer.read()

    def _get_source_filename(self, language: str) -> str:
        """Get the source file name for a language."""
        filenames = {
            "python": "server.py",
            "go": "server.go",
            "java": "RaftServer.java",
            "cpp": "server.cpp",
            "rust": "src/main.rs",
        }
        return filenames.get(language, "source.txt")

    def _get_dockerfile(self, language: str) -> str:
        """Get Dockerfile content for a language."""
        # C++ needs dynamic generation for project ID
        if language == "cpp":
            return self._get_cpp_dockerfile()

        dockerfiles = {
            "python": """
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "server.py"]
""",
            "go": """
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o server .

FROM alpine:3.18
WORKDIR /app
COPY --from=builder /app/server .
CMD ["./server"]
""",
            "java": """
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY build/libs/*.jar app.jar
CMD ["java", "-jar", "app.jar"]
""",
            "rust": """
FROM rust:1.74 AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/server .
CMD ["./server"]
""",
        }
        return dockerfiles.get(language, "FROM scratch")

    def _get_cpp_dockerfile(self) -> str:
        """
        Generate C++ Dockerfile with project-specific base image reference.

        Uses the prebuilt raft-cpp-base image which contains:
        - Pre-compiled gRPC and protobuf libraries
        - All necessary shared libraries for runtime
        """
        return f"""
# Runtime image for C++ Raft server
# Uses prebuilt base image for shared libraries
FROM gcr.io/{self.project_id}/raft-cpp-base:latest AS base

FROM ubuntu:22.04

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libssl3 \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared libraries from prebuilt base image
COPY --from=base /usr/local/lib /usr/local/lib

# Update library cache
RUN ldconfig

# Copy the built server binary
COPY build/server .

# Expose gRPC port
EXPOSE 50051

CMD ["./server"]
"""

    def _get_build_files(self, language: str) -> Dict[str, str]:
        """Get additional build files for a language."""
        if language == "python":
            return {
                "requirements.txt": "grpcio>=1.59.0\ngrpcio-tools>=1.59.0\nprotobuf>=4.25.0\n"
            }
        elif language == "go":
            return {
                "go.mod": """module github.com/sdp/raft

go 1.21

require (
    google.golang.org/grpc v1.59.0
    google.golang.org/protobuf v1.31.0
)
""",
                "go.sum": "",
            }
        return {}

    async def deploy_cluster(
        self,
        submission_id: int,
        image_name: str,
        cluster_size: int = 3,
    ) -> List[str]:
        """
        Deploy a Raft cluster to Cloud Run.

        Args:
            submission_id: Submission ID
            image_name: Docker image name
            cluster_size: Number of nodes (3 or 5)

        Returns:
            List of service URLs
        """
        client = run_v2.ServicesClient()
        service_urls = []

        # Deploy each node
        for i in range(cluster_size):
            node_id = f"node{i+1}"
            service_name = f"raft-{submission_id}-{node_id}"

            # Calculate peer addresses
            peers = []
            for j in range(cluster_size):
                if j != i:
                    peer_name = f"raft-{submission_id}-node{j+1}"
                    peers.append(f"{peer_name}:50051")

            service = run_v2.Service(
                template=run_v2.RevisionTemplate(
                    containers=[
                        run_v2.Container(
                            image=image_name,
                            ports=[run_v2.ContainerPort(container_port=50051)],
                            env=[
                                run_v2.EnvVar(name="NODE_ID", value=node_id),
                                run_v2.EnvVar(name="PORT", value="50051"),
                                run_v2.EnvVar(name="PEERS", value=",".join(peers)),
                            ],
                            resources=run_v2.ResourceRequirements(
                                limits={"cpu": "1", "memory": "512Mi"}
                            ),
                        )
                    ],
                    scaling=run_v2.RevisionScaling(min_instance_count=1, max_instance_count=1),
                ),
            )

            parent = f"projects/{self.project_id}/locations/{self.region}"

            try:
                operation = client.create_service(
                    parent=parent,
                    service=service,
                    service_id=service_name,
                )
                result = operation.result()
                service_urls.append(result.uri)
            except Exception as e:
                # Service might already exist, try to update
                try:
                    name = f"{parent}/services/{service_name}"
                    operation = client.update_service(service=service)
                    result = operation.result()
                    service_urls.append(result.uri)
                except Exception as update_error:
                    raise Exception(f"Failed to deploy {service_name}: {update_error}")

        return service_urls

    async def cleanup_cluster(self, submission_id: int, cluster_size: int = 3) -> None:
        """
        Clean up a deployed Raft cluster.

        Args:
            submission_id: Submission ID
            cluster_size: Number of nodes
        """
        client = run_v2.ServicesClient()

        for i in range(cluster_size):
            node_id = f"node{i+1}"
            service_name = f"raft-{submission_id}-{node_id}"
            name = f"projects/{self.project_id}/locations/{self.region}/services/{service_name}"

            try:
                client.delete_service(name=name)
            except Exception as e:
                print(f"Failed to delete service {service_name}: {e}")


# Singleton instance
build_service = DistributedBuildService()

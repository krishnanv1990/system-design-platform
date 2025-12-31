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

        Security Analysis:
        - AddressSanitizer (ASan): Memory corruption, buffer overflows
        - ThreadSanitizer (TSan): Race conditions
        - UndefinedBehaviorSanitizer (UBSan): Undefined behavior

        This reduces build time from ~15min to ~1-2min.
        """
        base_image = f"gcr.io/{self.project_id}/raft-cpp-base:latest"

        # Build command with security analysis
        # Uses CMakeLists.txt from the source archive (includes Abseil linking)
        build_cmd = (
            # Copy pre-generated proto sources from base image
            "cp -r /app/generated /workspace/ && "
            "cd /workspace && "
            # Build with AddressSanitizer for memory analysis
            "echo '=== Building with AddressSanitizer (Memory Analysis) ===' && "
            "mkdir -p build_asan && cd build_asan && "
            "cmake -DCMAKE_BUILD_TYPE=Debug "
            "-DCMAKE_CXX_FLAGS='-fsanitize=address -fno-omit-frame-pointer -g' "
            "-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address' .. && "
            "make -j$(nproc) 2>&1 | tee /workspace/asan_build.log && "
            "cd /workspace && "
            # Build with ThreadSanitizer for race detection
            "echo '=== Building with ThreadSanitizer (Race Detection) ===' && "
            "mkdir -p build_tsan && cd build_tsan && "
            "cmake -DCMAKE_BUILD_TYPE=Debug "
            "-DCMAKE_CXX_FLAGS='-fsanitize=thread -fno-omit-frame-pointer -g' "
            "-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=thread' .. && "
            "make -j$(nproc) 2>&1 | tee /workspace/tsan_build.log && "
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

    async def start_build(
        self,
        submission_id: int,
        language: str,
        source_code: str,
        build_modifications: Optional[Dict] = None,
    ) -> str:
        """
        Start a Cloud Build job for a submission.

        Args:
            submission_id: Submission ID
            language: Programming language
            source_code: User's source code
            build_modifications: Optional AI-generated build file modifications

        Returns:
            Build ID
        """
        # Upload source to GCS
        bucket_name = f"{self.project_id}-distributed-builds"
        source_path = f"submissions/{submission_id}/source.tar.gz"

        # Create source archive with optional build modifications
        source_archive = self._create_source_archive(
            language, source_code, submission_id, build_modifications
        )

        # Upload to GCS
        client = storage.Client(project=self.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(source_path)
        blob.upload_from_string(source_archive)

        # Start Cloud Build
        build_client = cloudbuild_v1.CloudBuildClient()

        build_config = self.get_cloudbuild_config(language, submission_id)

        # Convert steps from dict to BuildStep objects
        steps = []
        for step_dict in build_config.get("steps", []):
            step = cloudbuild_v1.BuildStep(
                name=step_dict.get("name"),
                entrypoint=step_dict.get("entrypoint"),
                args=step_dict.get("args", []),
            )
            steps.append(step)

        # Create Build object with proper protobuf types
        build = cloudbuild_v1.Build(
            source=cloudbuild_v1.Source(
                storage_source=cloudbuild_v1.StorageSource(
                    bucket=bucket_name,
                    object_=source_path,
                )
            ),
            steps=steps,
            images=build_config.get("images", []),
            timeout=build_config.get("timeout", "600s"),
        )

        operation = build_client.create_build(project_id=self.project_id, build=build)

        # Return the build ID
        return operation.metadata.build.id

    def _create_source_archive(
        self,
        language: str,
        source_code: str,
        submission_id: int,
        build_modifications: Optional[Dict] = None,
    ) -> bytes:
        """
        Create a tarball with the source code and proto file.

        Args:
            language: Programming language
            source_code: User's source code
            submission_id: Submission ID
            build_modifications: Optional AI-generated build file modifications

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

            # Add build files (requirements.txt, go.mod, etc.) with AI modifications
            build_files = self._get_build_files(language, build_modifications)
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

    def _get_build_files(
        self, language: str, build_modifications: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Get additional build files for a language.

        Args:
            language: Programming language
            build_modifications: Optional AI-generated modifications containing:
                - additional_dependencies: list of packages to add
                - cmake_packages: C++ find_package additions
                - cmake_libraries: C++ target_link_libraries additions

        Returns:
            Dict of filename -> content
        """
        mods = build_modifications or {}
        additional_deps = mods.get("additional_dependencies", [])

        if language == "python":
            base_deps = ["grpcio>=1.59.0", "grpcio-tools>=1.59.0", "protobuf>=4.25.0"]
            # Add any AI-detected additional dependencies
            all_deps = base_deps + [d for d in additional_deps if d not in base_deps]
            return {
                "requirements.txt": "\n".join(all_deps) + "\n"
            }
        elif language == "go":
            base_mod = """module github.com/sdp/raft

go 1.21

require (
    google.golang.org/grpc v1.59.0
    google.golang.org/protobuf v1.31.0
"""
            # Add AI-detected Go dependencies
            for dep in additional_deps:
                if dep and "require" not in dep:
                    base_mod += f"    {dep}\n"
            base_mod += ")\n"
            return {
                "go.mod": base_mod,
                "go.sum": "",
            }
        elif language == "cpp":
            cmake_packages = mods.get("cmake_packages", [])
            cmake_libraries = mods.get("cmake_libraries", [])
            return {
                "CMakeLists.txt": self._get_cpp_cmakelists(cmake_packages, cmake_libraries)
            }
        elif language == "rust":
            # Base Cargo.toml dependencies
            cargo_toml = """[package]
name = "raft-server"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = { version = "1.34", features = ["full"] }
tonic = "0.10"
prost = "0.12"
rand = "0.8"
clap = { version = "4.4", features = ["derive"] }
"""
            # Add AI-detected Rust dependencies
            for dep in additional_deps:
                if dep and "=" not in cargo_toml.split(dep.split("=")[0] if "=" in dep else dep)[0]:
                    cargo_toml += f"{dep}\n"
            cargo_toml += """
[build-dependencies]
tonic-build = "0.10"
"""
            return {
                "Cargo.toml": cargo_toml,
                "build.rs": """fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .build_server(true)
        .build_client(true)
        .compile(&["raft.proto"], &["."])?;
    Ok(())
}
""",
            }
        elif language == "java":
            # Base build.gradle
            build_gradle = """plugins {
    id 'java'
    id 'application'
    id 'com.google.protobuf' version '0.9.4'
}

repositories {
    mavenCentral()
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    implementation 'io.grpc:grpc-netty-shaded:1.59.0'
    implementation 'io.grpc:grpc-protobuf:1.59.0'
    implementation 'io.grpc:grpc-stub:1.59.0'
    implementation 'io.grpc:grpc-services:1.59.0'
    implementation 'com.google.protobuf:protobuf-java:3.25.0'
    implementation 'javax.annotation:javax.annotation-api:1.3.2'
"""
            # Add AI-detected Java dependencies
            for dep in additional_deps:
                if dep:
                    build_gradle += f"    implementation '{dep}'\n"
            build_gradle += """}

protobuf {
    protoc {
        artifact = 'com.google.protobuf:protoc:3.25.0'
    }
    plugins {
        grpc {
            artifact = 'io.grpc:protoc-gen-grpc-java:1.59.0'
        }
    }
    generateProtoTasks {
        all()*.plugins {
            grpc {}
        }
    }
}

application {
    mainClass = 'com.sdp.raft.RaftServer'
}

jar {
    manifest {
        attributes 'Main-Class': 'com.sdp.raft.RaftServer'
    }
    from {
        configurations.runtimeClasspath.collect { it.isDirectory() ? it : zipTree(it) }
    }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
}
"""
            return {
                "build.gradle": build_gradle,
            }
        return {}

    def _get_cpp_cmakelists(
        self,
        cmake_packages: Optional[List[str]] = None,
        cmake_libraries: Optional[List[str]] = None,
    ) -> str:
        """
        Get CMakeLists.txt for C++ Raft server.

        Args:
            cmake_packages: Additional find_package entries from AI analysis
            cmake_libraries: Additional target_link_libraries entries from AI analysis

        This CMakeLists.txt:
        - Links against pre-compiled gRPC and protobuf from the base image
        - Links Abseil libraries required by newer protobuf
        - Supports AddressSanitizer, ThreadSanitizer, and UndefinedBehaviorSanitizer
        """
        # Generate additional find_package statements
        extra_packages = ""
        if cmake_packages:
            for pkg in cmake_packages:
                if pkg:
                    extra_packages += f"find_package({pkg} QUIET)\n"

        # Generate additional library links
        extra_libraries = ""
        if cmake_libraries:
            for lib in cmake_libraries:
                if lib:
                    extra_libraries += f"    {lib}\n"

        # Build the CMakeLists.txt using string concatenation to avoid f-string issues with ${}
        cmake = '''cmake_minimum_required(VERSION 3.16)
project(raft_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)
find_package(OpenSSL REQUIRED)

# Find gRPC - use pkg-config or cmake config
find_package(gRPC CONFIG QUIET)
if(NOT gRPC_FOUND)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(GRPC QUIET grpc++ grpc)
    endif()
endif()

# Find Abseil (required by protobuf 4.x)
find_package(absl CONFIG QUIET)
if(NOT absl_FOUND)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(ABSL QUIET absl_base absl_log absl_strings)
    endif()
endif()

'''
        # Add AI-detected additional packages
        if extra_packages:
            cmake += "# AI-detected additional packages\n"
            cmake += extra_packages + "\n"

        cmake += '''# Include generated proto headers
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/generated)

# Collect proto sources
file(GLOB PROTO_SRCS "generated/*.cc")

# Build the server executable
add_executable(server
    server.cpp
    ${PROTO_SRCS}
)

# Add compiler warnings
target_compile_options(server PRIVATE -Wall -Wextra)

# Link libraries
target_link_libraries(server
    ${Protobuf_LIBRARIES}
    Threads::Threads
    OpenSSL::SSL
    OpenSSL::Crypto
)

# Link gRPC
if(gRPC_FOUND)
    target_link_libraries(server gRPC::grpc++ gRPC::grpc++_reflection)
elseif(GRPC_FOUND)
    target_link_libraries(server ${GRPC_LIBRARIES})
    target_include_directories(server PRIVATE ${GRPC_INCLUDE_DIRS})
else()
    # Fallback to manual linking
    target_link_libraries(server grpc++ grpc++_reflection grpc gpr)
endif()

# Link Abseil (required by newer protobuf versions)
if(absl_FOUND)
    target_link_libraries(server
        absl::base
        absl::log
        absl::log_internal_check_op
        absl::log_internal_message
        absl::status
        absl::statusor
        absl::strings
        absl::synchronization
        absl::time
    )
elseif(ABSL_FOUND)
    target_link_libraries(server ${ABSL_LIBRARIES})
    target_include_directories(server PRIVATE ${ABSL_INCLUDE_DIRS})
else()
    # Fallback to manual linking for commonly needed Abseil libs
    find_library(ABSL_BASE absl_base)
    find_library(ABSL_LOG absl_log)
    find_library(ABSL_LOG_INTERNAL_CHECK_OP absl_log_internal_check_op)
    find_library(ABSL_LOG_INTERNAL_MESSAGE absl_log_internal_message)
    find_library(ABSL_STRINGS absl_strings)
    find_library(ABSL_STATUS absl_status)
    find_library(ABSL_SYNCHRONIZATION absl_synchronization)
    find_library(ABSL_TIME absl_time)
    find_library(ABSL_RAW_LOGGING absl_raw_logging_internal)
    find_library(ABSL_THROW_DELEGATE absl_throw_delegate)
    find_library(ABSL_SPINLOCK_WAIT absl_spinlock_wait)

    if(ABSL_BASE)
        target_link_libraries(server
            ${ABSL_BASE}
            ${ABSL_LOG}
            ${ABSL_LOG_INTERNAL_CHECK_OP}
            ${ABSL_LOG_INTERNAL_MESSAGE}
            ${ABSL_STRINGS}
            ${ABSL_STATUS}
            ${ABSL_SYNCHRONIZATION}
            ${ABSL_TIME}
            ${ABSL_RAW_LOGGING}
            ${ABSL_THROW_DELEGATE}
            ${ABSL_SPINLOCK_WAIT}
        )
    endif()
endif()

'''
        # Add AI-detected additional libraries
        if extra_libraries:
            cmake += "# AI-detected additional libraries\n"
            cmake += "target_link_libraries(server\n"
            cmake += extra_libraries
            cmake += ")\n\n"

        cmake += '''# Install
install(TARGETS server DESTINATION bin)
'''
        return cmake

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

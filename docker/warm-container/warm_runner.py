"""
Warm Container Runner

This script manages a warm container that:
1. Starts up immediately with a placeholder health endpoint
2. Watches for candidate code injection
3. Dynamically loads and runs the candidate's FastAPI application
4. Supports hot-reloading without container restart
"""

import os
import sys
import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("warm-runner")

# Environment configuration
PORT = int(os.getenv("PORT", "8080"))
MODE = os.getenv("MODE", "warm")  # "warm" or "active"
CANDIDATE_CODE_PATH = Path("/app/candidate/main.py")
WATCH_INTERVAL = 0.5  # seconds


class WarmContainerManager:
    """Manages the warm container lifecycle and code injection."""

    def __init__(self):
        self.app: FastAPI = self._create_placeholder_app()
        self.candidate_app: Optional[FastAPI] = None
        self.last_code_mtime: Optional[float] = None
        self.is_active = False

    def _create_placeholder_app(self) -> FastAPI:
        """Create a placeholder app for the warm state."""
        app = FastAPI(title="Warm Container - Awaiting Code")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "mode": "active" if self.is_active else "warm",
                "ready": self.is_active,
            }

        @app.get("/status")
        async def status():
            return {
                "is_active": self.is_active,
                "candidate_code_loaded": self.candidate_app is not None,
                "namespace": os.getenv("NAMESPACE", "unknown"),
                "submission_id": os.getenv("SUBMISSION_ID", "unknown"),
            }

        @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def proxy_to_candidate(path: str):
            if not self.is_active or not self.candidate_app:
                return Response(
                    content='{"error": "Container is warming up, code not yet loaded"}',
                    status_code=503,
                    media_type="application/json"
                )
            # In active mode, this shouldn't be reached as candidate app takes over
            return Response(
                content='{"error": "Route not found"}',
                status_code=404,
                media_type="application/json"
            )

        return app

    def load_candidate_code(self) -> bool:
        """
        Dynamically load the candidate's code from the injected file.
        Returns True if successful, False otherwise.
        """
        if not CANDIDATE_CODE_PATH.exists():
            logger.debug(f"Candidate code not found at {CANDIDATE_CODE_PATH}")
            return False

        try:
            # Check if file has been modified
            current_mtime = CANDIDATE_CODE_PATH.stat().st_mtime
            if self.last_code_mtime == current_mtime:
                return self.is_active  # No change

            logger.info(f"Loading candidate code from {CANDIDATE_CODE_PATH}")

            # Load the module dynamically
            spec = importlib.util.spec_from_file_location("candidate_main", CANDIDATE_CODE_PATH)
            if spec is None or spec.loader is None:
                logger.error("Failed to create module spec")
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules["candidate_main"] = module
            spec.loader.exec_module(module)

            # Get the FastAPI app from the module
            if hasattr(module, "app"):
                self.candidate_app = module.app
                self.last_code_mtime = current_mtime
                self.is_active = True
                logger.info("Candidate code loaded successfully!")
                return True
            else:
                logger.error("Candidate code does not have an 'app' object")
                return False

        except Exception as e:
            logger.error(f"Error loading candidate code: {e}")
            return False

    async def watch_for_code(self):
        """Watch for candidate code injection and load it when available."""
        logger.info(f"Watching for candidate code at {CANDIDATE_CODE_PATH}")
        while True:
            self.load_candidate_code()
            await asyncio.sleep(WATCH_INTERVAL)


# Global manager instance
manager = WarmContainerManager()


# Create a combined app that delegates to candidate app when active
app = FastAPI(title="Warm Container")


@app.middleware("http")
async def delegate_to_candidate(request, call_next):
    """Middleware to delegate requests to candidate app when active."""
    if manager.is_active and manager.candidate_app:
        # Forward to candidate app
        from starlette.routing import Mount
        # For simplicity, we mount the candidate app
        # In production, would use a more sophisticated routing approach
        pass
    return await call_next(request)


# Mount the placeholder/manager app
app.mount("/", manager.app)


async def start_watcher():
    """Start the code watcher in the background."""
    asyncio.create_task(manager.watch_for_code())


@app.on_event("startup")
async def startup():
    """Start background tasks on startup."""
    logger.info(f"Warm container starting on port {PORT}")
    logger.info(f"Mode: {MODE}")
    logger.info(f"Namespace: {os.getenv('NAMESPACE', 'not set')}")
    await start_watcher()


if __name__ == "__main__":
    # Use a custom application factory to support hot reloading
    class WarmContainerApp:
        """Custom ASGI app that can switch between warm and active modes."""

        def __init__(self):
            self.manager = manager

        async def __call__(self, scope, receive, send):
            if self.manager.is_active and self.manager.candidate_app:
                # Delegate to candidate app
                await self.manager.candidate_app(scope, receive, send)
            else:
                # Use placeholder app
                await self.manager.app(scope, receive, send)

    # Start the watcher before running uvicorn
    import threading

    def run_watcher():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.watch_for_code())

    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()

    # Run uvicorn with the warm container app
    uvicorn.run(
        WarmContainerApp(),
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )

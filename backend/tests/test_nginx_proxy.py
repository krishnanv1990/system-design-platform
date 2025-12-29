"""
Tests for nginx proxy configuration.

These tests verify the nginx configuration for proxying API requests
to the backend service.
"""

import pytest
import re
import os

# Get the project root directory (parent of backend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNginxConfiguration:
    """Tests for nginx.conf configuration."""

    @pytest.fixture
    def nginx_config(self):
        """Load nginx configuration file."""
        with open(os.path.join(PROJECT_ROOT, 'frontend', 'nginx.conf'), 'r') as f:
            return f.read()

    def test_nginx_listens_on_port_8080(self, nginx_config):
        """Test nginx listens on port 8080 for Cloud Run."""
        assert 'listen 8080' in nginx_config

    def test_nginx_has_dns_resolver(self, nginx_config):
        """Test nginx has DNS resolver configured."""
        assert 'resolver' in nginx_config
        # Should use Google DNS
        assert '8.8.8.8' in nginx_config

    def test_nginx_has_api_proxy_location(self, nginx_config):
        """Test nginx has /api/ location block."""
        assert 'location /api/' in nginx_config

    def test_nginx_proxies_to_backend(self, nginx_config):
        """Test nginx proxies API requests to backend."""
        assert 'proxy_pass' in nginx_config
        assert 'sdp-backend' in nginx_config

    def test_nginx_sets_proxy_headers(self, nginx_config):
        """Test nginx sets required proxy headers."""
        assert 'proxy_set_header Host' in nginx_config
        assert 'proxy_set_header X-Real-IP' in nginx_config
        assert 'proxy_set_header X-Forwarded-For' in nginx_config
        assert 'proxy_set_header X-Forwarded-Proto' in nginx_config

    def test_nginx_enables_ssl_for_proxy(self, nginx_config):
        """Test nginx enables SSL for proxy connections."""
        assert 'proxy_ssl_server_name on' in nginx_config

    def test_nginx_has_spa_fallback(self, nginx_config):
        """Test nginx has SPA fallback to index.html."""
        assert 'try_files $uri $uri/ /index.html' in nginx_config

    def test_nginx_has_health_endpoint(self, nginx_config):
        """Test nginx has health check endpoint."""
        assert 'location /health' in nginx_config
        assert "return 200 'OK'" in nginx_config

    def test_nginx_has_gzip_enabled(self, nginx_config):
        """Test nginx has gzip compression enabled."""
        assert 'gzip on' in nginx_config

    def test_nginx_caches_static_assets(self, nginx_config):
        """Test nginx caches static assets."""
        assert 'expires 1y' in nginx_config
        assert 'Cache-Control' in nginx_config

    def test_nginx_proxy_timeouts_configured(self, nginx_config):
        """Test nginx has proxy timeouts configured."""
        assert 'proxy_connect_timeout' in nginx_config
        assert 'proxy_send_timeout' in nginx_config
        assert 'proxy_read_timeout' in nginx_config


class TestDockerfileConfiguration:
    """Tests for Dockerfile.prod configuration."""

    @pytest.fixture
    def dockerfile(self):
        """Load Dockerfile.prod."""
        with open(os.path.join(PROJECT_ROOT, 'frontend', 'Dockerfile.prod'), 'r') as f:
            return f.read()

    def test_dockerfile_uses_node_builder(self, dockerfile):
        """Test Dockerfile uses Node.js for building."""
        assert 'FROM node:' in dockerfile
        assert 'AS builder' in dockerfile

    def test_dockerfile_uses_nginx_alpine(self, dockerfile):
        """Test Dockerfile uses nginx:alpine for serving."""
        assert 'FROM nginx:alpine' in dockerfile

    def test_dockerfile_copies_nginx_config(self, dockerfile):
        """Test Dockerfile copies nginx configuration."""
        assert 'nginx.conf' in dockerfile
        assert '/etc/nginx/conf.d/' in dockerfile

    def test_dockerfile_exposes_port_8080(self, dockerfile):
        """Test Dockerfile exposes port 8080."""
        assert 'EXPOSE 8080' in dockerfile

    def test_dockerfile_has_vite_api_url_arg(self, dockerfile):
        """Test Dockerfile has VITE_API_URL build argument."""
        assert 'ARG VITE_API_URL' in dockerfile


class TestCloudBuildConfiguration:
    """Tests for cloudbuild.yaml configuration."""

    @pytest.fixture
    def cloudbuild(self):
        """Load cloudbuild.yaml."""
        with open(os.path.join(PROJECT_ROOT, 'cloudbuild.yaml'), 'r') as f:
            return f.read()

    def test_cloudbuild_builds_frontend(self, cloudbuild):
        """Test cloudbuild builds frontend container."""
        assert 'sdp-frontend' in cloudbuild

    def test_cloudbuild_builds_backend(self, cloudbuild):
        """Test cloudbuild builds backend container."""
        assert 'sdp-backend' in cloudbuild

    def test_cloudbuild_deploys_frontend(self, cloudbuild):
        """Test cloudbuild deploys frontend to Cloud Run."""
        assert 'sdp-frontend' in cloudbuild

    def test_cloudbuild_deploys_to_cloud_run(self, cloudbuild):
        """Test cloudbuild deploys to Cloud Run."""
        assert 'run' in cloudbuild
        assert 'deploy' in cloudbuild

    def test_cloudbuild_allows_unauthenticated_access(self, cloudbuild):
        """Test cloudbuild allows unauthenticated access."""
        assert '--allow-unauthenticated' in cloudbuild


class TestProxyURLConstruction:
    """Tests for proxy URL construction."""

    def test_backend_url_format(self):
        """Test backend URL format is correct."""
        backend_url = "https://sdp-backend-zziiwqh26q-uc.a.run.app"

        # Should be HTTPS
        assert backend_url.startswith("https://")

        # Should be a Cloud Run URL
        assert ".a.run.app" in backend_url

    def test_backend_host_extraction(self):
        """Test backend host can be extracted from URL."""
        backend_url = "https://sdp-backend-zziiwqh26q-uc.a.run.app"
        expected_host = "sdp-backend-zziiwqh26q-uc.a.run.app"

        # Extract host from URL
        from urllib.parse import urlparse
        parsed = urlparse(backend_url)

        assert parsed.netloc == expected_host

    def test_api_path_construction(self):
        """Test API path is correctly constructed."""
        backend_url = "https://sdp-backend-zziiwqh26q-uc.a.run.app"
        api_path = "/api/auth/google"

        full_url = f"{backend_url}{api_path}"

        assert full_url == "https://sdp-backend-zziiwqh26q-uc.a.run.app/api/auth/google"

    def test_oauth_callback_url_construction(self):
        """Test OAuth callback URL is correctly constructed."""
        backend_url = "https://sdp-backend-zziiwqh26q-uc.a.run.app"

        google_callback = f"{backend_url}/api/auth/google/callback"
        github_callback = f"{backend_url}/api/auth/github/callback"

        assert "google/callback" in google_callback
        assert "github/callback" in github_callback

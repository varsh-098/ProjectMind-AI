"""
tests/test_production_readiness.py
==================================
Phase 26: Production Deployment & Dockerization Verification Suite.

COVERS:
  1. Dockerfile configuration: non-root user, healthcheck, port expose, layer caching.
  2. docker-compose.yml: multi-service orchestration (FastAPI + MongoDB), volumes, networks.
  3. .dockerignore: secret shielding, repository exclusions, bytecode hygiene.
  4. .env.production.example: production environment documentation and security configs.
  5. API Production Health: FastAPI root health check endpoint specification.
"""

import os
import unittest
from pathlib import Path


class TestProductionReadiness(unittest.TestCase):
    """Verifies production deployment artifacts and container specifications."""

    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_dockerfile_exists_and_configured(self):
        dockerfile = self.root / "Dockerfile"
        self.assertTrue(dockerfile.is_file(), "Dockerfile must exist at workspace root.")

        content = dockerfile.read_text(encoding="utf-8")

        # Base image
        self.assertIn("FROM python:3.12-slim", content)

        # Non-root user
        self.assertIn("useradd", content)
        self.assertIn("USER projectmind", content)

        # Port expose
        self.assertIn("EXPOSE 8000", content)

        # Container Healthcheck
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("http://localhost:8000/", content)

        # Layer optimization (requirements.txt copied before source code)
        req_pos = content.find("COPY requirements.txt")
        app_pos = content.find("COPY --chown=projectmind:projectmind backend/")
        self.assertGreater(app_pos, req_pos, "requirements.txt must be copied before application code for caching.")

    def test_docker_compose_exists_and_configured(self):
        compose_file = self.root / "docker-compose.yml"
        self.assertTrue(compose_file.is_file(), "docker-compose.yml must exist at workspace root.")

        content = compose_file.read_text(encoding="utf-8")

        # Services defined
        self.assertIn("services:", content)
        self.assertIn("api:", content)
        self.assertIn("mongodb:", content)

        # Ports
        self.assertIn('"8000:8000"', content)
        self.assertIn('"27017:27017"', content)

        # Service dependencies & healthchecks
        self.assertIn("condition: service_healthy", content)
        self.assertIn("mongo_data:", content)
        self.assertIn("projectmind_net:", content)

    def test_dockerignore_shields_sensitive_files(self):
        dockerignore = self.root / ".dockerignore"
        self.assertTrue(dockerignore.is_file(), ".dockerignore must exist at workspace root.")

        content = dockerignore.read_text(encoding="utf-8")

        # Shielded secrets and version control
        self.assertIn(".git", content)
        self.assertIn(".env", content)
        self.assertIn("*.pem", content)
        self.assertIn("*.key", content)
        self.assertIn("__pycache__/", content)

    def test_production_env_template_documented(self):
        env_example = self.root / ".env.production.example"
        self.assertTrue(env_example.is_file(), ".env.production.example must exist at workspace root.")

        content = env_example.read_text(encoding="utf-8")

        # Core production variables
        self.assertIn("PORT=", content)
        self.assertIn("ENV=production", content)
        self.assertIn("CORS_ALLOWED_ORIGINS=", content)
        self.assertIn("COOKIE_SECURE=", content)
        self.assertIn("COOKIE_SAMESITE=", content)
        self.assertIn("MONGODB_URI=", content)
        self.assertIn("MONGODB_DATABASE=", content)

    def test_api_health_check_endpoint_defined(self):
        main_py = self.root / "backend" / "main.py"
        self.assertTrue(main_py.is_file(), "backend/main.py must exist.")

        content = main_py.read_text(encoding="utf-8")
        self.assertIn("@app.get(", content)
        self.assertIn("async def health_check():", content)
        self.assertIn('"status": "running"', content)
        self.assertIn('"project": "ProjectMind AI"', content)


if __name__ == "__main__":
    unittest.main()

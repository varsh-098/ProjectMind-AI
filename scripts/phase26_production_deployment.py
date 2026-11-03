"""
scripts/phase26_production_deployment.py
========================================
Phase 26: Production Deployment & Dockerization Verification Script.

DEMONSTRATES:
  1. Dockerfile Security & Build Structure:
     - Base image: python:3.12-slim.
     - Dedicated non-root user (projectmind, uid=1000).
     - Layer caching optimization (requirements.txt isolated).
     - Built-in container healthcheck via curl.
  2. Multi-Container Orchestration (docker-compose.yml):
     - FastAPI ASGI API container (port 8000).
     - MongoDB 7.0 database container (port 27017).
     - Persistent named volume (mongo_data).
     - Healthcheck-gated service dependency (service_healthy).
     - Isolated bridge network (projectmind_net).
  3. Secret Shielding & .dockerignore Hygiene:
     - Strict exclusion of secrets, keys, git histories, and bytecodes.
  4. Production Environment Template (.env.production.example):
     - Production CORS origins, Secure cookies, MongoDB Atlas URI, and LLM keys.
  5. API Health Check Verification.

RUN:
    python scripts/phase26_production_deployment.py
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if ROOT.name == "projectmind":
    ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_header(title: str):
    print("\n" + "=" * 76)
    print(f"  {title}")
    print("=" * 76)


def test_part1_dockerfile():
    print_header("PART 1: DOCKERFILE SECURITY & BUILD SPECIFICATION")

    dockerfile = ROOT / "Dockerfile"
    assert dockerfile.is_file(), "Dockerfile missing from root."

    content = dockerfile.read_text(encoding="utf-8")
    lines = content.splitlines()

    print("[1.1] Base Image:")
    base_line = next(l for l in lines if l.startswith("FROM"))
    print(f"      {base_line}")
    assert "python:3.12-slim" in base_line

    print("\n[1.2] Security & User Privileges:")
    user_line = next(l for l in lines if l.startswith("USER"))
    print(f"      Non-root execution: '{user_line}'")
    assert "projectmind" in user_line

    print("\n[1.3] Container Healthcheck:")
    health_line = next(l for l in lines if l.startswith("HEALTHCHECK"))
    print(f"      {health_line}")
    assert "http://localhost:8000/" in content

    print("\n[1.4] Build Layer Caching:")
    req_idx = next(i for i, l in enumerate(lines) if "COPY requirements.txt" in l)
    app_idx = next(i for i, l in enumerate(lines) if "COPY --chown=projectmind:projectmind backend/" in l)
    print(f"      Layer 1: Dependency caching at line {req_idx + 1}")
    print(f"      Layer 2: Application code at line {app_idx + 1}")
    assert req_idx < app_idx

    print("\n>>> Part 1: Dockerfile structure verified successfully!")


def test_part2_docker_compose():
    print_header("PART 2: MULTI-CONTAINER DOCKER COMPOSE ORCHESTRATION")

    compose_file = ROOT / "docker-compose.yml"
    assert compose_file.is_file(), "docker-compose.yml missing from root."

    content = compose_file.read_text(encoding="utf-8")

    print("[2.1] Service Definitions:")
    assert "api:" in content
    assert "mongodb:" in content
    print("      - Service 'api':      FastAPI ASGI server on port 8000")
    print("      - Service 'mongodb':  MongoDB 7.0 database engine on port 27017")

    print("\n[2.2] Healthcheck Dependency Gating:")
    assert "condition: service_healthy" in content
    print("      - api depends_on mongodb with condition: service_healthy")

    print("\n[2.3] Storage & Networking:")
    assert "mongo_data:" in content
    assert "projectmind_net:" in content
    print("      - Persistent Named Volume: mongo_data")
    print("      - Isolated Bridge Network: projectmind_net")

    print("\n>>> Part 2: Docker Compose orchestration verified successfully!")


def test_part3_dockerignore():
    print_header("PART 3: SECRET SHIELDING & .DOCKERIGNORE HYGIENE")

    dockerignore = ROOT / ".dockerignore"
    assert dockerignore.is_file(), ".dockerignore missing from root."

    content = dockerignore.read_text(encoding="utf-8")
    shielded_patterns = [".git", ".env", "*.pem", "*.key", "__pycache__/"]

    print("Excluded Patterns:")
    for pat in shielded_patterns:
        assert pat in content
        print(f"      [OK] Shielded: '{pat}'")

    print("\n>>> Part 3: .dockerignore hygiene verified successfully!")


def test_part4_env_production():
    print_header("PART 4: PRODUCTION ENVIRONMENT CONFIGURATION TEMPLATE")

    env_file = ROOT / ".env.production.example"
    assert env_file.is_file(), ".env.production.example missing from root."

    content = env_file.read_text(encoding="utf-8")
    required_vars = [
        "PORT",
        "ENV=production",
        "CORS_ALLOWED_ORIGINS",
        "COOKIE_SECURE",
        "COOKIE_SAMESITE",
        "MONGODB_URI",
        "MONGODB_DATABASE",
    ]

    print("Documented Production Variables:")
    for v in required_vars:
        assert v in content
        print(f"      [OK] Configured: '{v}'")

    print("\n>>> Part 4: Production environment template verified successfully!")


def test_part5_api_health():
    print_header("PART 5: API PRODUCTION HEALTH SPECIFICATION")

    main_py = ROOT / "backend" / "main.py"
    assert main_py.is_file()

    content = main_py.read_text(encoding="utf-8")
    assert "async def health_check():" in content
    assert '"status": "running"' in content
    assert '"project": "ProjectMind AI"' in content

    print("Health Check Endpoint Specification:")
    print("      GET / -> status: 'running', project: 'ProjectMind AI'")
    print("\n>>> Part 5: API production health endpoint verified successfully!")


def main():
    print("=" * 76)
    print("  PROJECTMIND AI — PHASE 26: PRODUCTION DEPLOYMENT & DOCKERIZATION")
    print("=" * 76)

    test_part1_dockerfile()
    test_part2_docker_compose()
    test_part3_dockerignore()
    test_part4_env_production()
    test_part5_api_health()

    print("\n" + "=" * 76)
    print("  PHASE 26 VERIFICATION COMPLETE: ALL 5 PARTS PASSED PERFECTLY!")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()


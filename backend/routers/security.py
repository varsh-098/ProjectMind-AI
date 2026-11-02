"""
backend/routers/security.py
===========================
Phase 24: REST API Router for Security & Sandboxing.

ENDPOINTS:
    POST /security/validate-code       → Analyze Python source code with AST safety checker
    POST /security/validate-path       → Verify whether a file path violates workspace boundaries
    GET  /security/permissions         → Query tool permissions and agent capability tiers
    GET  /security/policy              → Inspect active sandboxing policies and shielded patterns
"""

from typing import Dict, Any, List, Optional

try:
    from fastapi import APIRouter, HTTPException, status
    from pydantic import BaseModel, Field
except ImportError:
    class APIRouter:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return dict(self.__dict__)

    def Field(default=None, **kwargs):
        return default

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class status:
        HTTP_200_OK = 200
        HTTP_400_BAD_REQUEST = 400
        HTTP_403_FORBIDDEN = 403

from backend.security.ast_validator import ast_validator
from backend.security.sandbox import (
    workspace_sandbox,
    command_sanitizer,
    SHIELDED_FILES_AND_PATTERNS,
    DANGEROUS_COMMAND_PATTERNS,
)
from backend.security.permissions import (
    permission_checker,
    TOOL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
)

router = APIRouter(
    prefix="/security",
    tags=["Security & Sandboxing"],
)


# -------------------------------------------------------
# Schemas
# -------------------------------------------------------

class CodeValidationRequest(BaseModel):
    code: str = Field(..., description="Python source code to inspect.")
    file_path: Optional[str] = Field(None, description="Optional target file path.")


class PathValidationRequest(BaseModel):
    path: str = Field(..., description="File path to validate against workspace boundaries.")


class ToolPermissionCheckRequest(BaseModel):
    agent_role: str = Field(..., description="Role or name of the agent (e.g. 'coding_agent').")
    tool_name: str = Field(..., description="Name of the tool to execute.")


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.post(
    "/validate-code",
    summary="Validate Python code for dangerous AST primitives",
)
async def validate_code(req: CodeValidationRequest) -> Dict[str, Any]:
    """
    Inspects Python code with the AST security analyzer.
    Detects eval/exec calls, reflection exploits, and unauthorized module imports.
    """
    result = ast_validator.validate_code(req.code)
    return {
        "is_safe": result.is_safe,
        "summary": result.summary,
        "violation_count": len(result.violations),
        "violations": [v.to_dict() for v in result.violations],
        "file_path": req.file_path,
    }


@router.post(
    "/validate-path",
    summary="Validate path safety against workspace sandbox",
)
async def validate_path(req: PathValidationRequest) -> Dict[str, Any]:
    """
    Checks if a path attempts directory traversal or accesses shielded files.
    """
    is_safe, error = workspace_sandbox.is_safe_path(req.path)
    return {
        "path": req.path,
        "is_safe": is_safe,
        "error": error,
    }


@router.post(
    "/check-permission",
    summary="Check if an agent role is permitted to run a tool",
)
async def check_permission(req: ToolPermissionCheckRequest) -> Dict[str, Any]:
    """
    Evaluates role capability tiers against tool requirements.
    """
    is_permitted = permission_checker.is_permitted(req.agent_role, req.tool_name)
    required = permission_checker.get_required_permission(req.tool_name)
    allowed = list(p.value for p in permission_checker.get_role_permissions(req.agent_role))

    return {
        "agent_role": req.agent_role,
        "tool_name": req.tool_name,
        "is_permitted": is_permitted,
        "required_permission": required.value,
        "allowed_permissions": allowed,
    }


@router.get(
    "/policy",
    summary="Get active security sandboxing policies",
)
async def get_security_policy() -> Dict[str, Any]:
    """
    Returns the active security sandbox configuration, shielded files, and blocked commands.
    """
    return {
        "workspace_root": str(workspace_sandbox.root),
        "shielded_patterns": SHIELDED_FILES_AND_PATTERNS,
        "blocked_command_patterns": DANGEROUS_COMMAND_PATTERNS,
        "tool_permissions": {k: v.value for k, v in TOOL_PERMISSIONS.items()},
        "default_role_permissions": {
            k: [p.value for p in v] for k, v in DEFAULT_ROLE_PERMISSIONS.items()
        },
    }

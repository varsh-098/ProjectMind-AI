"""
backend/mcp/protocol.py
========================
JSON-RPC 2.0 Message Types for the Model Context Protocol (MCP).

MCP uses JSON-RPC 2.0 as its wire format. This module defines:
  - Request / Response / Notification / Error message dataclasses
  - Serialization helpers (to_dict / from_dict)
  - Standard MCP error codes

WHY JSON-RPC?
  JSON-RPC is a lightweight remote-procedure-call protocol that uses JSON.
  Every message is self-contained: it has a method name, parameters, and
  an id so the caller can match responses to requests.

  MCP chose JSON-RPC because:
    1. It's language-agnostic (works with Python, JS, Rust, …)
    2. It supports bidirectional communication (server can also send requests)
    3. It's simpler than gRPC/protobuf for tool-calling use cases
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
import json
import uuid


# ──────────────────────────────────────────────────────────────
# 1. Standard JSON-RPC 2.0 Error Codes
# ──────────────────────────────────────────────────────────────

class ErrorCode:
    """Standard JSON-RPC 2.0 error codes + MCP-specific codes."""

    # JSON-RPC standard errors (-32700 to -32600)
    PARSE_ERROR = -32700        # Invalid JSON
    INVALID_REQUEST = -32600    # Not a valid JSON-RPC request
    METHOD_NOT_FOUND = -32601   # Method does not exist
    INVALID_PARAMS = -32602     # Invalid method parameters
    INTERNAL_ERROR = -32603     # Internal server error

    # MCP-specific errors (-32000 to -32099)
    TOOL_NOT_FOUND = -32000     # Tool name not recognized
    RESOURCE_NOT_FOUND = -32001 # Resource URI not found
    TOOL_EXECUTION_ERROR = -32002  # Tool ran but failed
    CAPABILITY_NOT_SUPPORTED = -32003  # Server doesn't support this


# ──────────────────────────────────────────────────────────────
# 2. JSON-RPC Message Dataclasses
# ──────────────────────────────────────────────────────────────

@dataclass
class JsonRpcRequest:
    """
    A JSON-RPC 2.0 Request.

    Fields:
        method  — The remote method to call (e.g. "tools/list")
        params  — Optional dict of parameters
        id      — Unique request identifier (auto-generated if not provided)
        jsonrpc — Always "2.0"

    Example:
        {"jsonrpc": "2.0", "id": "abc-123", "method": "tools/list", "params": {}}
    """
    method: str
    params: Optional[Dict[str, Any]] = None
    id: str = ""
    jsonrpc: str = "2.0"

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]  # Short unique ID

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-RPC dict."""
        d = {"jsonrpc": self.jsonrpc, "id": self.id, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcResponse:
    """
    A JSON-RPC 2.0 Success Response.

    Fields:
        result  — The return value from the method
        id      — Must match the request id
        jsonrpc — Always "2.0"

    Example:
        {"jsonrpc": "2.0", "id": "abc-123", "result": {"tools": [...]}}
    """
    result: Any
    id: str
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {"jsonrpc": self.jsonrpc, "id": self.id, "result": self.result}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcError:
    """
    A JSON-RPC 2.0 Error object (nested inside an error response).

    Fields:
        code    — Numeric error code (see ErrorCode class)
        message — Human-readable error description
        data    — Optional additional error data
    """
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass
class JsonRpcErrorResponse:
    """
    A JSON-RPC 2.0 Error Response.

    Example:
        {"jsonrpc": "2.0", "id": "abc-123", "error": {"code": -32601, "message": "Method not found"}}
    """
    error: JsonRpcError
    id: Optional[str] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "error": self.error.to_dict()
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class JsonRpcNotification:
    """
    A JSON-RPC 2.0 Notification (a request with NO id — no response expected).

    Used for events like progress updates or log messages.

    Example:
        {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progress": 50}}
    """
    method: str
    params: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ──────────────────────────────────────────────────────────────
# 3. Message Parsing Helpers
# ──────────────────────────────────────────────────────────────

def parse_message(raw: Union[str, dict]) -> Union[
    JsonRpcRequest, JsonRpcResponse, JsonRpcErrorResponse, JsonRpcNotification
]:
    """
    Parse a raw JSON-RPC 2.0 message into the appropriate dataclass.

    Args:
        raw: Either a JSON string or already-parsed dict

    Returns:
        One of: JsonRpcRequest, JsonRpcResponse, JsonRpcErrorResponse, JsonRpcNotification

    Raises:
        ValueError: If the message is not valid JSON-RPC 2.0
    """
    # Step 1: Parse JSON string if needed
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    elif isinstance(raw, dict):
        data = raw
    else:
        raise ValueError(f"Expected str or dict, got {type(raw).__name__}")

    # Step 2: Validate jsonrpc version
    if data.get("jsonrpc") != "2.0":
        raise ValueError("Missing or invalid 'jsonrpc' field (must be '2.0')")

    # Step 3: Determine message type
    has_method = "method" in data
    has_id = "id" in data
    has_result = "result" in data
    has_error = "error" in data

    if has_error:
        # Error response
        err = data["error"]
        return JsonRpcErrorResponse(
            error=JsonRpcError(
                code=err["code"],
                message=err["message"],
                data=err.get("data")
            ),
            id=data.get("id")
        )

    if has_result:
        # Success response
        return JsonRpcResponse(result=data["result"], id=data["id"])

    if has_method and has_id:
        # Request (has both method and id)
        return JsonRpcRequest(
            method=data["method"],
            params=data.get("params"),
            id=data["id"]
        )

    if has_method and not has_id:
        # Notification (method but no id)
        return JsonRpcNotification(
            method=data["method"],
            params=data.get("params")
        )

    raise ValueError("Cannot determine JSON-RPC message type from fields present")


def create_error_response(
    request_id: Optional[str],
    code: int,
    message: str,
    data: Optional[Any] = None
) -> JsonRpcErrorResponse:
    """Convenience function to create an error response."""
    return JsonRpcErrorResponse(
        error=JsonRpcError(code=code, message=message, data=data),
        id=request_id
    )


def create_success_response(request_id: str, result: Any) -> JsonRpcResponse:
    """Convenience function to create a success response."""
    return JsonRpcResponse(result=result, id=request_id)

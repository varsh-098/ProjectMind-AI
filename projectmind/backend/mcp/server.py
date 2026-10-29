"""
backend/mcp/server.py
======================
MCP (Model Context Protocol) Server for ProjectMind AI.

This server exposes ProjectMind's tools and resources via the MCP standard,
allowing ANY MCP-compatible AI client (Claude Desktop, Cursor, VSCode Copilot)
to discover and use our tools.

WHAT IS MCP?
  MCP is an open protocol (created by Anthropic) that standardizes how
  AI applications connect to external data sources and tools.

  Think of it like USB for AI:
    - Before USB: every device needed its own cable type
    - After USB:  one standard port works for everything

  Before MCP: every AI app had custom integrations
  After MCP:  one protocol lets any AI use any tool

ARCHITECTURE:
  ┌──────────────┐     JSON-RPC 2.0      ┌──────────────────┐
  │  AI Client   │ ◄──────────────────►   │  MCP Server      │
  │  (Claude,    │    initialize          │  (this file)     │
  │   Cursor)    │    tools/list          │                  │
  │              │    tools/call          │  Wraps:          │
  │              │    resources/list      │  - tools.py      │
  │              │    resources/read      │  - file_manager  │
  └──────────────┘                        │  - memory        │
                                          └──────────────────┘

MCP METHODS WE IMPLEMENT:
  1. initialize         — Handshake: exchange capabilities
  2. tools/list         — Discover available tools
  3. tools/call         — Execute a tool with arguments
  4. resources/list     — List available resources (files, memory)
  5. resources/read     — Read a specific resource by URI
  6. ping               — Health check
"""

import os
import sys
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

# Import our protocol layer
from backend.mcp.protocol import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcErrorResponse,
    JsonRpcError,
    JsonRpcNotification,
    ErrorCode,
    parse_message,
    create_error_response,
    create_success_response,
)

# Import our existing tools system
from backend.brain.tools import TOOL_SCHEMAS, TOOL_REGISTRY, execute_tool


# ──────────────────────────────────────────────────────────────
# 1. Server Configuration
# ──────────────────────────────────────────────────────────────

@dataclass
class ServerCapabilities:
    """
    What this MCP server can do.
    The client reads these during initialization to know what to expect.
    """
    tools: bool = True           # We can execute tools
    resources: bool = True       # We can serve resources
    prompts: bool = False        # We don't serve prompt templates (yet)
    logging: bool = False        # We don't support structured logging (yet)

    def to_dict(self) -> Dict[str, Any]:
        caps = {}
        if self.tools:
            caps["tools"] = {}
        if self.resources:
            caps["resources"] = {}
        if self.prompts:
            caps["prompts"] = {}
        if self.logging:
            caps["logging"] = {}
        return caps


@dataclass
class ServerInfo:
    """Server metadata returned during initialization."""
    name: str = "projectmind-mcp"
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "version": self.version}


# ──────────────────────────────────────────────────────────────
# 2. Resource Registry
# ──────────────────────────────────────────────────────────────

@dataclass
class MCPResource:
    """
    An MCP Resource — a piece of data the AI can read.

    Resources are identified by URIs like:
      - projectmind://files/backend/main.py
      - projectmind://memory/decisions
      - projectmind://config/settings
    """
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


# ──────────────────────────────────────────────────────────────
# 3. The MCP Server
# ──────────────────────────────────────────────────────────────

class MCPServer:
    """
    ProjectMind's MCP Server.

    This is a synchronous, in-process server (no network sockets).
    In production, you'd wrap this with a transport layer (stdio, SSE, WebSocket).

    Usage:
        server = MCPServer()
        response = server.handle_message(request_dict)
    """

    def __init__(self, project_root: Optional[str] = None):
        self.server_info = ServerInfo()
        self.capabilities = ServerCapabilities()
        self.initialized = False
        self.project_root = project_root or os.getcwd()

        # Build the resource registry
        self._resources: List[MCPResource] = self._build_resource_list()

        # Method dispatch table — maps MCP method names to handler functions
        self._handlers: Dict[str, callable] = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
        }

    def _build_resource_list(self) -> List[MCPResource]:
        """Build the list of available resources."""
        resources = [
            MCPResource(
                uri="projectmind://project/structure",
                name="Project Structure",
                description="Overview of the project directory structure",
            ),
            MCPResource(
                uri="projectmind://memory/decisions",
                name="Project Decisions",
                description="Architectural decisions stored in project memory",
                mime_type="application/json",
            ),
            MCPResource(
                uri="projectmind://memory/facts",
                name="Project Facts",
                description="Key facts about the project stored in memory",
                mime_type="application/json",
            ),
            MCPResource(
                uri="projectmind://config/agents",
                name="Agent Configuration",
                description="Configuration of available AI agents",
                mime_type="application/json",
            ),
        ]
        return resources

    # ──────────────────────────────────────────────────────
    # Main Message Handler
    # ──────────────────────────────────────────────────────

    def handle_message(self, raw_message: Any) -> Dict[str, Any]:
        """
        Process an incoming JSON-RPC 2.0 message and return a response.

        This is the MAIN ENTRY POINT for the server.

        Args:
            raw_message: A dict or JSON string containing a JSON-RPC request

        Returns:
            A dict containing the JSON-RPC response
        """
        # Step 1: Parse the message
        try:
            msg = parse_message(raw_message)
        except ValueError as e:
            return create_error_response(
                None, ErrorCode.PARSE_ERROR, str(e)
            ).to_dict()

        # Step 2: Handle based on message type
        if isinstance(msg, JsonRpcRequest):
            return self._dispatch_request(msg)
        elif isinstance(msg, JsonRpcNotification):
            # Notifications don't get responses, but we acknowledge them
            return create_success_response("notification", {"status": "received"}).to_dict()
        else:
            return create_error_response(
                None, ErrorCode.INVALID_REQUEST, "Expected a request message"
            ).to_dict()

    def _dispatch_request(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """Route a request to the appropriate handler."""
        handler = self._handlers.get(request.method)

        if handler is None:
            return create_error_response(
                request.id,
                ErrorCode.METHOD_NOT_FOUND,
                f"Unknown method: {request.method}",
                data={"available_methods": list(self._handlers.keys())}
            ).to_dict()

        try:
            result = handler(request)
            return create_success_response(request.id, result).to_dict()
        except Exception as e:
            return create_error_response(
                request.id,
                ErrorCode.INTERNAL_ERROR,
                f"Handler error: {str(e)}"
            ).to_dict()

    # ──────────────────────────────────────────────────────
    # Handler Methods
    # ──────────────────────────────────────────────────────

    def _handle_initialize(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """
        MCP Initialization Handshake.

        The client sends its capabilities, we respond with ours.
        This MUST be the first method called.

        Returns:
            Server info + capabilities
        """
        self.initialized = True

        # Extract client info if provided
        client_info = {}
        if request.params:
            client_info = request.params.get("clientInfo", {})

        return {
            "protocolVersion": "2024-11-05",  # MCP protocol version
            "serverInfo": self.server_info.to_dict(),
            "capabilities": self.capabilities.to_dict(),
            "instructions": (
                "ProjectMind AI MCP Server. Use tools/list to discover "
                "available code-generation tools, and resources/list to "
                "browse project files and memory."
            ),
        }

    def _handle_ping(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """Simple health check."""
        return {"status": "ok"}

    def _handle_tools_list(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """
        Return all available tools in MCP format.

        Our TOOL_SCHEMAS use OpenAI function-calling format:
            {"type": "function", "function": {"name": ..., "parameters": ...}}

        MCP expects:
            {"name": ..., "description": ..., "inputSchema": {"type": "object", ...}}

        This method converts between the two formats.
        """
        mcp_tools = []

        for schema in TOOL_SCHEMAS:
            # Handle OpenAI function-calling format (nested under "function" key)
            if "function" in schema:
                func_def = schema["function"]
            else:
                func_def = schema  # Flat format fallback

            params = func_def.get("parameters", {})
            mcp_tool = {
                "name": func_def["name"],
                "description": func_def.get("description", ""),
                "inputSchema": {
                    "type": "object",
                    "properties": params.get("properties", {}),
                    "required": params.get("required", []),
                },
            }
            mcp_tools.append(mcp_tool)

        return {"tools": mcp_tools}

    def _handle_tools_call(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """
        Execute a tool by name with the given arguments.

        Expected params:
            {
                "name": "create_file",
                "arguments": {"path": "hello.py", "content": "print('hi')"}
            }
        """
        if not request.params:
            raise ValueError("Missing 'params' — need 'name' and 'arguments'")

        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if not tool_name:
            raise ValueError("Missing 'name' in params")

        # Check if tool exists
        if tool_name not in TOOL_REGISTRY:
            return create_error_response(
                request.id,
                ErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {tool_name}",
                data={"available_tools": list(TOOL_REGISTRY.keys())}
            ).to_dict()

        # Execute the tool
        try:
            result = execute_tool(tool_name, arguments)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ],
                "isError": False,
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool execution error: {str(e)}",
                    }
                ],
                "isError": True,
            }

    def _handle_resources_list(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """
        List all available resources.

        Returns resource URIs, names, descriptions, and MIME types.
        """
        return {
            "resources": [r.to_dict() for r in self._resources]
        }

    def _handle_resources_read(self, request: JsonRpcRequest) -> Dict[str, Any]:
        """
        Read a specific resource by URI.

        Expected params:
            {"uri": "projectmind://project/structure"}
        """
        if not request.params:
            raise ValueError("Missing 'params' — need 'uri'")

        uri = request.params.get("uri")
        if not uri:
            raise ValueError("Missing 'uri' in params")

        # Find the resource
        resource = None
        for r in self._resources:
            if r.uri == uri:
                resource = r
                break

        if resource is None:
            return create_error_response(
                request.id,
                ErrorCode.RESOURCE_NOT_FOUND,
                f"Resource not found: {uri}",
                data={"available_resources": [r.uri for r in self._resources]}
            ).to_dict()

        # Read the resource content
        content = self._read_resource_content(resource)

        return {
            "contents": [
                {
                    "uri": resource.uri,
                    "mimeType": resource.mime_type,
                    "text": content,
                }
            ]
        }

    def _read_resource_content(self, resource: MCPResource) -> str:
        """Read the actual content of a resource."""
        import json

        if resource.uri == "projectmind://project/structure":
            return self._get_project_structure()

        elif resource.uri == "projectmind://memory/decisions":
            # Try to read from memory module
            try:
                from backend.brain.memory import MemoryStore
                store = MemoryStore()
                decisions = store.search("decision", top_k=10)
                return json.dumps(decisions, indent=2)
            except Exception:
                return json.dumps({"info": "Memory store not initialized"})

        elif resource.uri == "projectmind://memory/facts":
            try:
                from backend.brain.memory import MemoryStore
                store = MemoryStore()
                facts = store.search("fact", top_k=10)
                return json.dumps(facts, indent=2)
            except Exception:
                return json.dumps({"info": "Memory store not initialized"})

        elif resource.uri == "projectmind://config/agents":
            return json.dumps({
                "agents": [
                    {"name": "coding_agent", "type": "CodingAgent", "tools": ["create_file", "edit_file", "run_command"]},
                    {"name": "review_agent", "type": "ReviewAgent", "tools": ["read_file"]},
                    {"name": "testing_agent", "type": "TestingAgent", "tools": ["run_tests", "run_command"]},
                ],
                "supervisor": "SupervisorOrchestrator",
            }, indent=2)

        return f"Content not available for: {resource.uri}"

    def _get_project_structure(self) -> str:
        """Generate a text representation of the project structure."""
        lines = ["Project: ProjectMind AI", f"Root: {self.project_root}", ""]
        target_dirs = ["backend", "projectmind/scripts"]

        for target in target_dirs:
            full_path = os.path.join(self.project_root, target)
            if os.path.exists(full_path):
                lines.append(f"📁 {target}/")
                try:
                    for item in sorted(os.listdir(full_path)):
                        item_path = os.path.join(full_path, item)
                        if os.path.isdir(item_path):
                            lines.append(f"  📁 {item}/")
                            # List files in subdirectory (1 level deep)
                            try:
                                for sub_item in sorted(os.listdir(item_path)):
                                    if sub_item.endswith('.py'):
                                        lines.append(f"    📄 {sub_item}")
                            except PermissionError:
                                pass
                        elif item.endswith('.py'):
                            lines.append(f"  📄 {item}")
                except PermissionError:
                    lines.append("  (permission denied)")
                lines.append("")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────
    # Convenience Methods
    # ──────────────────────────────────────────────────────

    def list_tools(self) -> List[Dict[str, Any]]:
        """Quick access to tool list (for testing)."""
        req = JsonRpcRequest(method="tools/list")
        resp = self.handle_message(req.to_dict())
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Quick access to call a tool (for testing)."""
        req = JsonRpcRequest(
            method="tools/call",
            params={"name": name, "arguments": arguments or {}}
        )
        return self.handle_message(req.to_dict())

    def list_resources(self) -> List[Dict[str, Any]]:
        """Quick access to resource list (for testing)."""
        req = JsonRpcRequest(method="resources/list")
        resp = self.handle_message(req.to_dict())
        return resp.get("result", {}).get("resources", [])

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Quick access to read a resource (for testing)."""
        req = JsonRpcRequest(
            method="resources/read",
            params={"uri": uri}
        )
        return self.handle_message(req.to_dict())

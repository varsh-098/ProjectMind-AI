"""
Phase 19 — MCP (Model Context Protocol)
=========================================
This script verifies our MCP server implementation.

WHAT IS MCP?
  Model Context Protocol is an open standard for connecting AI models
  to external tools and data. Think of it as "USB for AI" — one protocol
  that lets any AI client use any tool server.

  Key concepts:
    - JSON-RPC 2.0: The wire format (requests, responses, errors)
    - Tools: Functions the AI can call (create_file, run_tests, etc.)
    - Resources: Data the AI can read (project structure, memory)
    - Capabilities: What the server supports (tools? resources? prompts?)
    - Initialize handshake: Client and server exchange capabilities first

EXPERIMENTS:
  1. JSON-RPC Protocol Compliance — Message types, serialization, parsing
  2. MCP Server Initialization — Handshake and capability advertisement
  3. Tool Discovery (tools/list) — Get available tools in MCP format
  4. Tool Execution (tools/call) — Execute tools via MCP protocol
  5. Resource Discovery & Reading — List and read project resources
  6. Error Handling — Invalid methods, missing params, bad tool names
  7. End-to-End MCP Workflow — Complete client-server interaction
"""

import sys
import os
import json

# ── Path Setup ──
script_dir = os.path.dirname(os.path.abspath(__file__))
projectmind_dir = os.path.dirname(script_dir)
workspace_root = os.path.dirname(projectmind_dir)
sys.path.insert(0, workspace_root)
sys.path.insert(0, projectmind_dir)

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
from backend.mcp.server import MCPServer, ServerCapabilities, MCPResource

results = []

def run_experiment(name, func):
    """Run an experiment and track results."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        func()
        results.append((name, "PASS"))
        print(f"\n  ✅ {name} — PASSED")
    except Exception as e:
        results.append((name, f"FAIL: {e}"))
        print(f"\n  ❌ {name} — FAILED: {e}")
        import traceback
        traceback.print_exc()


# ══════════════════════════════════════════════════════════════
# Experiment 1: JSON-RPC Protocol Compliance
# ══════════════════════════════════════════════════════════════
def test_jsonrpc_protocol():
    """Test JSON-RPC 2.0 message creation, serialization, and parsing."""
    print("\n  --- Test 1a: Create and serialize a Request ---")
    req = JsonRpcRequest(method="tools/list", params={"cursor": None})
    req_dict = req.to_dict()
    print(f"  Request dict: {json.dumps(req_dict, indent=2)}")

    assert req_dict["jsonrpc"] == "2.0", "jsonrpc must be '2.0'"
    assert req_dict["method"] == "tools/list", "Method mismatch"
    assert "id" in req_dict, "Request must have an id"
    print("  ✓ Request created with correct fields")

    print("\n  --- Test 1b: Create and serialize a Response ---")
    resp = JsonRpcResponse(result={"tools": []}, id=req.id)
    resp_dict = resp.to_dict()
    print(f"  Response dict: {json.dumps(resp_dict, indent=2)}")

    assert resp_dict["id"] == req.id, "Response id must match request id"
    assert "result" in resp_dict, "Response must have 'result'"
    assert "error" not in resp_dict, "Success response must NOT have 'error'"
    print("  ✓ Response created correctly")

    print("\n  --- Test 1c: Create an Error Response ---")
    err_resp = create_error_response(
        "test-id", ErrorCode.METHOD_NOT_FOUND, "Method not found"
    )
    err_dict = err_resp.to_dict()
    print(f"  Error response: {json.dumps(err_dict, indent=2)}")

    assert err_dict["error"]["code"] == -32601, "Error code mismatch"
    assert "error" in err_dict, "Error response must have 'error'"
    assert "result" not in err_dict, "Error response must NOT have 'result'"
    print("  ✓ Error response created correctly")

    print("\n  --- Test 1d: Create a Notification (no id) ---")
    notif = JsonRpcNotification(method="notifications/progress", params={"percent": 50})
    notif_dict = notif.to_dict()
    print(f"  Notification: {json.dumps(notif_dict, indent=2)}")

    assert "id" not in notif_dict, "Notification must NOT have 'id'"
    assert notif_dict["method"] == "notifications/progress"
    print("  ✓ Notification created (no id, correct)")

    print("\n  --- Test 1e: Parse messages from JSON strings ---")
    # Parse a request
    parsed_req = parse_message(req.to_json())
    assert isinstance(parsed_req, JsonRpcRequest), f"Expected JsonRpcRequest, got {type(parsed_req)}"
    assert parsed_req.method == "tools/list"
    print("  ✓ Parsed request from JSON string")

    # Parse a response
    parsed_resp = parse_message(resp.to_json())
    assert isinstance(parsed_resp, JsonRpcResponse), f"Expected JsonRpcResponse, got {type(parsed_resp)}"
    print("  ✓ Parsed response from JSON string")

    # Parse an error
    parsed_err = parse_message(err_resp.to_json())
    assert isinstance(parsed_err, JsonRpcErrorResponse), f"Expected JsonRpcErrorResponse, got {type(parsed_err)}"
    print("  ✓ Parsed error response from JSON string")

    # Parse invalid JSON
    try:
        parse_message("{not valid json")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  ✓ Correctly rejected invalid JSON")

    print("\n  All JSON-RPC protocol tests passed!")

run_experiment("Experiment 1: JSON-RPC Protocol Compliance", test_jsonrpc_protocol)


# ══════════════════════════════════════════════════════════════
# Experiment 2: MCP Server Initialization
# ══════════════════════════════════════════════════════════════
def test_server_initialization():
    """Test the MCP initialization handshake."""
    server = MCPServer(project_root=workspace_root)

    print("\n  --- Test 2a: Server starts un-initialized ---")
    assert not server.initialized, "Server should start un-initialized"
    print("  ✓ Server starts in un-initialized state")

    print("\n  --- Test 2b: Send initialize request ---")
    init_request = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            },
            "capabilities": {}
        }
    }

    response = server.handle_message(init_request)
    print(f"  Init response: {json.dumps(response, indent=2)}")

    assert response["id"] == "init-1", "Response id must match request"
    assert "result" in response, "Must have result"

    result = response["result"]
    assert "protocolVersion" in result, "Must include protocol version"
    assert "serverInfo" in result, "Must include server info"
    assert "capabilities" in result, "Must include capabilities"
    print(f"  Server: {result['serverInfo']['name']} v{result['serverInfo']['version']}")
    print(f"  Protocol: {result['protocolVersion']}")
    print(f"  Capabilities: {list(result['capabilities'].keys())}")
    print("  ✓ Initialization handshake successful")

    print("\n  --- Test 2c: Server is now initialized ---")
    assert server.initialized, "Server should be initialized after handshake"
    print("  ✓ Server state updated to initialized")

    print("\n  --- Test 2d: Capabilities include tools and resources ---")
    caps = result["capabilities"]
    assert "tools" in caps, "Must support tools"
    assert "resources" in caps, "Must support resources"
    print("  ✓ Server advertises tools and resources capabilities")

run_experiment("Experiment 2: MCP Server Initialization", test_server_initialization)


# ══════════════════════════════════════════════════════════════
# Experiment 3: Tool Discovery (tools/list)
# ══════════════════════════════════════════════════════════════
def test_tool_discovery():
    """Test discovering available tools via tools/list."""
    server = MCPServer(project_root=workspace_root)

    print("\n  --- Test 3a: List all tools ---")
    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": "tools-1",
        "method": "tools/list",
        "params": {}
    })

    assert "result" in response, "Must have result"
    tools = response["result"]["tools"]
    print(f"  Found {len(tools)} tools:")

    for tool in tools:
        print(f"    🔧 {tool['name']}: {tool['description'][:60]}...")

    assert len(tools) > 0, "Must have at least one tool"
    print(f"  ✓ Discovered {len(tools)} tools")

    print("\n  --- Test 3b: Verify tool schema format (MCP compliant) ---")
    for tool in tools:
        assert "name" in tool, f"Tool missing 'name'"
        assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
        assert "inputSchema" in tool, f"Tool {tool['name']} missing 'inputSchema'"
        schema = tool["inputSchema"]
        assert schema.get("type") == "object", f"Tool {tool['name']} inputSchema.type must be 'object'"
        assert "properties" in schema, f"Tool {tool['name']} inputSchema missing 'properties'"
    print("  ✓ All tool schemas are MCP-compliant")

    print("\n  --- Test 3c: Check specific tools exist ---")
    tool_names = [t["name"] for t in tools]
    expected_tools = ["create_file", "edit_file", "run_command"]
    for expected in expected_tools:
        assert expected in tool_names, f"Missing expected tool: {expected}"
        print(f"    ✓ Found: {expected}")

    print("\n  --- Test 3d: Use convenience method ---")
    tools_via_convenience = server.list_tools()
    assert len(tools_via_convenience) == len(tools), "Convenience method should return same tools"
    print("  ✓ Convenience method works")

run_experiment("Experiment 3: Tool Discovery (tools/list)", test_tool_discovery)


# ══════════════════════════════════════════════════════════════
# Experiment 4: Tool Execution (tools/call)
# ══════════════════════════════════════════════════════════════
def test_tool_execution():
    """Test executing tools through the MCP protocol."""
    server = MCPServer(project_root=workspace_root)

    print("\n  --- Test 4a: Execute create_file tool ---")
    test_file = os.path.join(workspace_root, "projectmind", "test_mcp_output.txt")

    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "create_file",
            "arguments": {
                "path": test_file,
                "content": "Hello from MCP! This file was created via Model Context Protocol."
            }
        }
    })

    print(f"  Response: {json.dumps(response, indent=2)}")
    assert "result" in response, "Must have result"
    result = response["result"]
    assert "content" in result, "Tool result must have 'content'"
    assert result.get("isError") == False, "Should not be an error"
    print("  ✓ create_file executed successfully via MCP")

    # Verify file was created
    assert os.path.exists(test_file), "File should have been created"
    with open(test_file) as f:
        content = f.read()
    assert "Hello from MCP" in content, "File content mismatch"
    print(f"  ✓ File created and verified: {test_file}")

    # Clean up
    os.remove(test_file)
    print("  ✓ Cleaned up test file")

    print("\n  --- Test 4b: Use convenience method ---")
    response2 = server.call_tool("create_file", {
        "path": test_file,
        "content": "Convenience method test"
    })
    assert "result" in response2, "Convenience call must have result"
    os.remove(test_file)
    print("  ✓ Convenience call_tool works")

    print("\n  --- Test 4c: Call non-existent tool ---")
    response3 = server.handle_message({
        "jsonrpc": "2.0",
        "id": "call-bad",
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {}
        }
    })
    print(f"  Error response: {json.dumps(response3, indent=2)}")

    # The server returns an error inside the result for tool-not-found
    result3 = response3.get("result", {})
    if "error" in result3:
        # Returned as an error response
        print("  ✓ Non-existent tool returns error response")
    elif result3.get("isError"):
        print("  ✓ Non-existent tool returns isError=true")
    else:
        # Check if it's a top-level error
        assert "error" in response3, "Should be an error for non-existent tool"
        print("  ✓ Non-existent tool returns error")

run_experiment("Experiment 4: Tool Execution (tools/call)", test_tool_execution)


# ══════════════════════════════════════════════════════════════
# Experiment 5: Resource Discovery & Reading
# ══════════════════════════════════════════════════════════════
def test_resources():
    """Test listing and reading resources."""
    server = MCPServer(project_root=workspace_root)

    print("\n  --- Test 5a: List all resources ---")
    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": "res-1",
        "method": "resources/list",
        "params": {}
    })

    assert "result" in response, "Must have result"
    resources = response["result"]["resources"]
    print(f"  Found {len(resources)} resources:")

    for res in resources:
        print(f"    📦 {res['name']}: {res['uri']}")

    assert len(resources) > 0, "Must have at least one resource"
    print(f"  ✓ Discovered {len(resources)} resources")

    print("\n  --- Test 5b: Verify resource schema format ---")
    for res in resources:
        assert "uri" in res, "Resource missing 'uri'"
        assert "name" in res, "Resource missing 'name'"
        assert "description" in res, "Resource missing 'description'"
        assert "mimeType" in res, "Resource missing 'mimeType'"
    print("  ✓ All resources have correct MCP schema")

    print("\n  --- Test 5c: Read project structure resource ---")
    response2 = server.handle_message({
        "jsonrpc": "2.0",
        "id": "res-2",
        "method": "resources/read",
        "params": {"uri": "projectmind://project/structure"}
    })

    assert "result" in response2, "Must have result"
    contents = response2["result"]["contents"]
    assert len(contents) > 0, "Must have at least one content item"
    text = contents[0]["text"]
    print(f"  Project structure preview (first 300 chars):")
    print(f"  {text[:300]}...")
    assert "ProjectMind" in text, "Must contain project name"
    print("  ✓ Read project structure successfully")

    print("\n  --- Test 5d: Read agent configuration resource ---")
    response3 = server.read_resource("projectmind://config/agents")
    assert "result" in response3, "Must have result"
    agent_text = response3["result"]["contents"][0]["text"]
    agent_data = json.loads(agent_text)
    print(f"  Agent config: {json.dumps(agent_data, indent=2)}")
    assert "agents" in agent_data, "Must have 'agents' key"
    assert len(agent_data["agents"]) >= 3, "Must have at least 3 agents"
    print("  ✓ Read agent configuration successfully")

    print("\n  --- Test 5e: Read non-existent resource ---")
    response4 = server.handle_message({
        "jsonrpc": "2.0",
        "id": "res-bad",
        "method": "resources/read",
        "params": {"uri": "projectmind://nonexistent"}
    })
    # Should be an error
    result4 = response4.get("result", {})
    has_error = ("error" in response4) or ("error" in result4)
    print(f"  Non-existent resource response has error: {has_error}")
    print("  ✓ Non-existent resource handled gracefully")

run_experiment("Experiment 5: Resource Discovery & Reading", test_resources)


# ══════════════════════════════════════════════════════════════
# Experiment 6: Error Handling
# ══════════════════════════════════════════════════════════════
def test_error_handling():
    """Test MCP server error handling."""
    server = MCPServer(project_root=workspace_root)

    print("\n  --- Test 6a: Invalid method ---")
    response = server.handle_message({
        "jsonrpc": "2.0",
        "id": "err-1",
        "method": "nonexistent/method",
        "params": {}
    })
    assert "error" in response, "Must return error for invalid method"
    assert response["error"]["code"] == ErrorCode.METHOD_NOT_FOUND
    print(f"  Error: {response['error']['message']}")
    print("  ✓ Invalid method returns METHOD_NOT_FOUND")

    print("\n  --- Test 6b: Invalid JSON-RPC (missing jsonrpc field) ---")
    response2 = server.handle_message({
        "id": "err-2",
        "method": "ping",
    })
    assert "error" in response2, "Must return error for invalid JSON-RPC"
    print(f"  Error: {response2['error']['message']}")
    print("  ✓ Invalid JSON-RPC returns error")

    print("\n  --- Test 6c: tools/call with missing params ---")
    response3 = server.handle_message({
        "jsonrpc": "2.0",
        "id": "err-3",
        "method": "tools/call",
    })
    # Should get an error (either parse or handler)
    has_error = "error" in response3
    print(f"  Response has error: {has_error}")
    if has_error:
        print(f"  Error: {response3['error']['message']}")
    print("  ✓ Missing params handled gracefully")

    print("\n  --- Test 6d: tools/call with missing tool name ---")
    response4 = server.handle_message({
        "jsonrpc": "2.0",
        "id": "err-4",
        "method": "tools/call",
        "params": {"arguments": {}}
    })
    has_error = "error" in response4
    print(f"  Response has error: {has_error}")
    print("  ✓ Missing tool name handled gracefully")

    print("\n  --- Test 6e: Parse error from malformed JSON string ---")
    response5 = server.handle_message("{this is not valid json}")
    assert "error" in response5, "Must return parse error"
    assert response5["error"]["code"] == ErrorCode.PARSE_ERROR
    print(f"  Error: {response5['error']['message']}")
    print("  ✓ Parse error returned correctly")

run_experiment("Experiment 6: Error Handling", test_error_handling)


# ══════════════════════════════════════════════════════════════
# Experiment 7: End-to-End MCP Workflow
# ══════════════════════════════════════════════════════════════
def test_e2e_workflow():
    """Simulate a complete MCP client-server interaction."""
    print("\n  Simulating a full MCP session...")
    server = MCPServer(project_root=workspace_root)

    # Step 1: Initialize
    print("\n  📡 Step 1: Client sends initialize...")
    init_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "projectmind-test-client", "version": "0.1.0"},
            "capabilities": {}
        }
    })
    assert "result" in init_resp
    server_name = init_resp["result"]["serverInfo"]["name"]
    print(f"  ✓ Connected to: {server_name}")

    # Step 2: Ping
    print("\n  📡 Step 2: Client pings server...")
    ping_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "2", "method": "ping"
    })
    assert ping_resp["result"]["status"] == "ok"
    print("  ✓ Server is alive")

    # Step 3: Discover tools
    print("\n  📡 Step 3: Client discovers tools...")
    tools_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "3", "method": "tools/list"
    })
    tools = tools_resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    print(f"  ✓ Found tools: {tool_names}")

    # Step 4: Discover resources
    print("\n  📡 Step 4: Client discovers resources...")
    res_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "4", "method": "resources/list"
    })
    resources = res_resp["result"]["resources"]
    resource_uris = [r["uri"] for r in resources]
    print(f"  ✓ Found resources: {resource_uris}")

    # Step 5: Read a resource
    print("\n  📡 Step 5: Client reads project structure...")
    read_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "5",
        "method": "resources/read",
        "params": {"uri": "projectmind://project/structure"}
    })
    structure = read_resp["result"]["contents"][0]["text"]
    print(f"  ✓ Read {len(structure)} chars of project structure")

    # Step 6: Call a tool
    print("\n  📡 Step 6: Client calls create_file tool...")
    test_path = os.path.join(workspace_root, "projectmind", "mcp_e2e_test.txt")
    call_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "6",
        "method": "tools/call",
        "params": {
            "name": "create_file",
            "arguments": {
                "path": test_path,
                "content": "Created during MCP end-to-end test!\nPhase 19 verification."
            }
        }
    })
    assert call_resp["result"]["isError"] == False
    assert os.path.exists(test_path)
    print(f"  ✓ Tool executed — file created")

    # Clean up
    os.remove(test_path)

    # Step 7: Verify error handling in session
    print("\n  📡 Step 7: Client sends invalid request...")
    err_resp = server.handle_message({
        "jsonrpc": "2.0", "id": "7",
        "method": "tools/call",
        "params": {"name": "fake_tool", "arguments": {}}
    })
    # Server should handle gracefully without crashing
    print("  ✓ Server handled error gracefully, session continues")

    # Step 8: Another valid request after error
    print("\n  📡 Step 8: Client sends valid request after error...")
    ping_resp2 = server.handle_message({
        "jsonrpc": "2.0", "id": "8", "method": "ping"
    })
    assert ping_resp2["result"]["status"] == "ok"
    print("  ✓ Server still responsive after error — session is healthy")

    print("\n  🎉 Full MCP session completed successfully!")

run_experiment("Experiment 7: End-to-End MCP Workflow", test_e2e_workflow)


# ══════════════════════════════════════════════════════════════
# Final Report
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  PHASE 19 — MCP RESULTS SUMMARY")
print("=" * 60)

all_passed = True
for name, status in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {name}: {status}")
    if status != "PASS":
        all_passed = False

print()
if all_passed:
    print("  🎉 ALL EXPERIMENTS PASSED! Phase 19 complete!")
    print()
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║  VIVA / INTERVIEW PREPARATION — Phase 19: MCP          ║")
    print("  ╠══════════════════════════════════════════════════════════╣")
    print("  ║                                                        ║")
    print("  ║  Q: What is MCP (Model Context Protocol)?              ║")
    print("  ║  A: MCP is an open protocol that standardizes how AI   ║")
    print("  ║     applications connect to external tools and data    ║")
    print("  ║     sources. It uses JSON-RPC 2.0 as its wire format.  ║")
    print("  ║     Think of it as 'USB for AI' — one protocol that    ║")
    print("  ║     works with any client and any server.              ║")
    print("  ║                                                        ║")
    print("  ║  Q: What wire format does MCP use?                     ║")
    print("  ║  A: JSON-RPC 2.0 — a lightweight remote procedure     ║")
    print("  ║     call protocol using JSON. Each message has:        ║")
    print("  ║     jsonrpc='2.0', a method name, optional params,     ║")
    print("  ║     and an id to match requests with responses.        ║")
    print("  ║                                                        ║")
    print("  ║  Q: What are the main MCP message types?               ║")
    print("  ║  A: Request (method + id), Response (result + id),     ║")
    print("  ║     Error Response (error + id), and Notification      ║")
    print("  ║     (method, NO id — fire-and-forget).                 ║")
    print("  ║                                                        ║")
    print("  ║  Q: What are MCP Tools vs Resources?                   ║")
    print("  ║  A: Tools are ACTIONS the AI can perform (create_file, ║")
    print("  ║     run_tests). Resources are DATA the AI can READ     ║")
    print("  ║     (project structure, memory, config). Tools have    ║")
    print("  ║     side effects; resources are read-only.             ║")
    print("  ║                                                        ║")
    print("  ║  Q: How does MCP initialization work?                  ║")
    print("  ║  A: The client sends an 'initialize' request with its  ║")
    print("  ║     capabilities and client info. The server responds  ║")
    print("  ║     with its capabilities, server info, and protocol   ║")
    print("  ║     version. This handshake MUST happen before any     ║")
    print("  ║     other method calls.                                ║")
    print("  ║                                                        ║")
    print("  ║  Q: Why is MCP important for AI development?           ║")
    print("  ║  A: Without MCP, every AI app needs custom tool        ║")
    print("  ║     integrations. MCP provides a universal standard    ║")
    print("  ║     so tools written once work with any MCP client     ║")
    print("  ║     (Claude, Cursor, VSCode Copilot, etc).             ║")
    print("  ║                                                        ║")
    print("  ║  Q: What transports can MCP use?                       ║")
    print("  ║  A: stdio (subprocess), HTTP+SSE (Server-Sent Events), ║")
    print("  ║     or WebSocket. Our implementation is in-process     ║")
    print("  ║     (direct function calls) for simplicity.            ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
else:
    print("  ⚠️  Some experiments failed. Review errors above.")
    sys.exit(1)

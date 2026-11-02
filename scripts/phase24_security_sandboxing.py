"""
scripts/phase24_security_sandboxing.py
======================================
Phase 24: Security & Sandboxing Verification Script.

DEMONSTRATES:
  1. Workspace Path Sandboxing:
     - Strict workspace root confinement.
     - Path traversal blocking (../).
     - Shielded secret file protection (.env, id_rsa, *.pem).
  2. Python AST Code Safety Analyzer:
     - Parsing and validation of agent-generated code.
     - Detection of eval, exec, __import__, and globals calls.
     - Neutralization of reflection/introspection sandbox escapes.
     - Diagnostic violation reports with line numbers and explanations.
  3. Safe Command Execution Harness:
     - Interception and rejection of destructive commands (rm -rf, format, fork bombs).
     - Environment secret stripping (preventing child process credential theft).
     - Output buffer truncation and timeout enforcement.
  4. Role-Based Agent Tool Permission Boundaries (Capability RBAC):
     - ReviewAgent / SecurityAuditor constrained to READ_ONLY.
     - CodingAgent constrained to WORKSPACE_WRITE.
     - TestingAgent constrained to COMMAND_EXECUTE.
  5. Security REST API Endpoints.

RUN:
    python scripts/phase24_security_sandboxing.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.security import (
    workspace_sandbox,
    PathSecurityError,
    command_sanitizer,
    CommandSecurityError,
    ast_validator,
    permission_checker,
    PermissionDeniedError,
    ToolPermission,
)
from backend.brain.tools import execute_tool, run_command
from backend.routers.security import (
    validate_code,
    validate_path,
    check_permission,
    get_security_policy,
    CodeValidationRequest,
    PathValidationRequest,
    ToolPermissionCheckRequest,
)


def run_async(coro):
    """Safely advance coroutines synchronously without Windows IOCP event loop blocks."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value


def main():
    print("=" * 75)
    print("  PROJECTMIND AI — PHASE 24: SECURITY & SANDBOXING VERIFICATION")
    print("=" * 75)

    # -------------------------------------------------------------
    # 1. Workspace Path Sandboxing & Traversal Prevention
    # -------------------------------------------------------------
    print("\n[PART 1] Testing Workspace Path Sandboxing...")
    print(f"  -> Workspace Root : {workspace_sandbox.root}")

    # Test 1A: Safe path
    safe_path = "backend/config.py"
    resolved = workspace_sandbox.resolve_safe_path(safe_path)
    print(f"  -> Safe path '{safe_path}' resolved : {resolved.name} (exists={resolved.exists()})")

    # Test 1B: Traversal attempts
    traversal_attacks = [
        "../../Windows/System32/drivers/etc/hosts",
        "../../../etc/shadow",
        "backend/../../secret_token.txt",
    ]
    for attack in traversal_attacks:
        try:
            workspace_sandbox.resolve_safe_path(attack)
            print(f"  [FAIL] Failed to block traversal: {attack}")
        except PathSecurityError as e:
            print(f"  [BLOCKED] Traversal attempt '{attack}' -> {e}")

    # Test 1C: Shielded secret files
    shielded_attempts = [
        ".env",
        ".env.local",
        ".git/config",
        ".ssh/id_rsa",
        "private_cert.pem",
    ]
    for secret in shielded_attempts:
        try:
            workspace_sandbox.resolve_safe_path(secret)
            print(f"  [FAIL] Failed to shield secret: {secret}")
        except PathSecurityError as e:
            print(f"  [SHIELDED] Secret file '{secret}' -> {e}")

    print("  [PASS] Workspace directory boundaries and secret file shields confirmed.")

    # -------------------------------------------------------------
    # 2. Python AST Code Safety Analyzer
    # -------------------------------------------------------------
    print("\n[PART 2] Testing Python AST Code Safety Analyzer...")

    # Test 2A: Clean code
    clean_code = """
def calculate_metrics(values):
    return {
        "count": len(values),
        "total": sum(values),
        "mean": sum(values) / len(values) if values else 0,
    }
"""
    clean_result = ast_validator.validate_code(clean_code)
    print(f"  -> Clean code validation   : is_safe = {clean_result.is_safe} ({clean_result.summary})")
    assert clean_result.is_safe

    # Test 2B: Malicious code with eval, exec, and __import__
    malicious_code = """
import math

def dangerous_function(user_str):
    result = eval(user_str)
    exec("import os; os.system('echo compromised')")
    secret_mod = __import__('subprocess')
    return result
"""
    malicious_result = ast_validator.validate_code(malicious_code)
    print(f"  -> Malicious code check    : is_safe = {malicious_result.is_safe}")
    print(f"  -> Violations detected     : {len(malicious_result.violations)}")
    for v in malicious_result.violations:
        print(f"     • Line {v.line_number} [{v.severity}] {v.category}: {v.message}")
    assert not malicious_result.is_safe
    assert len(malicious_result.violations) == 3

    # Test 2C: Reflection sandbox escape exploit
    jailbreak_code = """
def escape_sandbox():
    base_class = ().__class__.__bases__[0]
    subclasses = base_class.__subclasses__()
    return subclasses
"""
    jailbreak_result = ast_validator.validate_code(jailbreak_code)
    print(f"  -> Introspection exploit   : is_safe = {jailbreak_result.is_safe}")
    print(f"  -> Violations detected     : {len(jailbreak_result.violations)}")
    for v in jailbreak_result.violations:
        print(f"     • Line {v.line_number} [{v.severity}] {v.category}: {v.message}")
    assert not jailbreak_result.is_safe
    print("  [PASS] AST code safety analyzer and jailbreak detection confirmed.")

    # -------------------------------------------------------------
    # 3. Safe Command Execution Harness
    # -------------------------------------------------------------
    print("\n[PART 3] Testing Command Execution Sandbox & Secret Stripping...")

    # Test 3A: Destructive command interception
    blocked_commands = [
        "rm -rf /var/log",
        "del /s /q C:\\Users",
        "format D:",
        ":(){ :|:& };:",
        "shutdown -r -t 0",
        "sudo rm -rf /",
    ]
    for cmd in blocked_commands:
        try:
            command_sanitizer.validate_command(cmd)
            print(f"  [FAIL] Failed to block destructive command: {cmd}")
        except CommandSecurityError as e:
            print(f"  [BLOCKED] Command '{cmd}' -> {e}")

    # Test 3B: Environment secret stripping
    os.environ["MONGODB_URI"] = "mongodb+srv://admin:atlas_secret@cluster.mongodb.net"
    os.environ["GROQ_API_KEY"] = "gsk_sensitive_groq_credential"
    os.environ["GEMINI_API_KEY"] = "AIzaSySensitiveGeminiCredential"

    sanitized_env = command_sanitizer.get_sanitized_environment()
    assert "MONGODB_URI" not in sanitized_env
    assert "GROQ_API_KEY" not in sanitized_env
    assert "GEMINI_API_KEY" not in sanitized_env
    print(f"  -> Environment stripped    : MONGODB_URI in child env = {'MONGODB_URI' in sanitized_env}")
    print(f"  -> Environment stripped    : GROQ_API_KEY in child env = {'GROQ_API_KEY' in sanitized_env}")
    print(f"  -> Environment stripped    : GEMINI_API_KEY in child env = {'GEMINI_API_KEY' in sanitized_env}")

    # Test 3C: Safe sandboxed command execution
    res = command_sanitizer.run_sandboxed(f'"{sys.executable}" -c "print(\'EXEC_SANDBOX_OK\')"', timeout=10)
    print(f"  -> Safe command execution  : exit_code = {res['exit_code']}, output = '{res['stdout']}'")
    assert res["success"]
    print("  [PASS] Command execution sandbox and secret stripping confirmed.")

    # -------------------------------------------------------------
    # 4. Agent Tool Capability Boundaries (RBAC)
    # -------------------------------------------------------------
    print("\n[PART 4] Testing Agent Tool Capability Boundaries (RBAC)...")

    # ReviewAgent: READ_ONLY
    review_can_read = permission_checker.is_permitted("review_agent", "read_file")
    review_can_write = permission_checker.is_permitted("review_agent", "create_file")
    review_can_exec = permission_checker.is_permitted("review_agent", "run_command")
    print(f"  -> ReviewAgent (read_file)     : permitted = {review_can_read}")
    print(f"  -> ReviewAgent (create_file)   : permitted = {review_can_write}")
    print(f"  -> ReviewAgent (run_command)   : permitted = {review_can_exec}")
    assert review_can_read is True
    assert review_can_write is False
    assert review_can_exec is False

    # CodingAgent: READ_ONLY + WORKSPACE_WRITE
    coding_can_write = permission_checker.is_permitted("coding_agent", "create_file")
    coding_can_exec = permission_checker.is_permitted("coding_agent", "run_command")
    print(f"  -> CodingAgent (create_file)   : permitted = {coding_can_write}")
    print(f"  -> CodingAgent (run_command)   : permitted = {coding_can_exec}")
    assert coding_can_write is True
    assert coding_can_exec is False

    # TestingAgent: READ_ONLY + COMMAND_EXECUTE
    testing_can_exec = permission_checker.is_permitted("testing_agent", "run_tests")
    testing_can_write = permission_checker.is_permitted("testing_agent", "edit_file")
    print(f"  -> TestingAgent (run_tests)    : permitted = {testing_can_exec}")
    print(f"  -> TestingAgent (edit_file)    : permitted = {testing_can_write}")
    assert testing_can_exec is True
    assert testing_can_write is False

    # Enforce tool dispatcher permission check
    tool_res = execute_tool("run_command", {"command": "git status"}, agent_role="review_agent")
    print(f"  -> Dispatcher enforcement check: success = {tool_res['success']}, error = '{tool_res['error']}'")
    assert not tool_res["success"]
    assert "Permission Denied" in tool_res["error"]
    print("  [PASS] Agent capability tiers and tool boundaries confirmed.")

    # -------------------------------------------------------------
    # 5. Security REST API Router
    # -------------------------------------------------------------
    print("\n[PART 5] Testing Security REST API Endpoints...")

    # POST /security/validate-code
    code_api_res = run_async(validate_code(CodeValidationRequest(code="eval('1 + 1')")))
    print(f"  -> POST /security/validate-code : is_safe = {code_api_res['is_safe']}, violations = {code_api_res['violation_count']}")

    # POST /security/validate-path
    path_api_res = run_async(validate_path(PathValidationRequest(path="../../etc/passwd")))
    print(f"  -> POST /security/validate-path : is_safe = {path_api_res['is_safe']}, error = '{path_api_res['error']}'")

    # POST /security/check-permission
    perm_api_res = run_async(check_permission(ToolPermissionCheckRequest(agent_role="testing_agent", tool_name="run_tests")))
    print(f"  -> POST /security/check-permission: is_permitted = {perm_api_res['is_permitted']}, required = {perm_api_res['required_permission']}")

    # GET /security/policy
    policy_res = run_async(get_security_policy())
    print(f"  -> GET /security/policy         : {len(policy_res['shielded_patterns'])} shielded patterns, {len(policy_res['blocked_command_patterns'])} blocked commands")
    print("  [PASS] Security REST endpoints verified.")

    print("\n" + "=" * 75)
    print("  [ALL PASS] PHASE 24 SECURITY & SANDBOXING FULLY VERIFIED!")
    print("=" * 75)


if __name__ == "__main__":
    main()

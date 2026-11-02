"""
backend/security/sandbox.py
===========================
Phase 24: Workspace Path Sandboxing & Command Sanitization.

PURPOSE:
    1. WorkspaceSandbox: Enforces directory boundaries, blocks path traversal (../),
       and shields sensitive files (.env, private keys, .git credentials).
    2. CommandSanitizer: Blocks dangerous system commands, strips environment secrets
       from child process execution, and enforces execution timeouts.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple


class PathSecurityError(PermissionError):
    """Raised when an agent attempts to access or modify a path outside workspace boundaries."""
    pass


class CommandSecurityError(PermissionError):
    """Raised when a command violates security sandboxing rules."""
    pass


# =====================================================================
# 1. Workspace Path Sandbox
# =====================================================================

SHIELDED_FILES_AND_PATTERNS = [
    # Environment secrets
    r"^\.env$",
    r"^\.env\.(?!example$).*$",  # Blocks .env.local, .env.production, etc., allows .env.example
    # Git secrets and hooks
    r"^\.git/.*$",
    r"^\.git$",
    # SSH and AWS credentials
    r"^\.ssh(/.*)?$",
    r"^\.aws(/.*)?$",
    r"^id_rsa.*$",
    r"^id_ed25519.*$",
    # Private certificates and keys
    r"^.*\.pem$",
    r"^.*\.key$",
    r"^.*\.pfx$",
    # Shell histories
    r"^\.bash_history$",
    r"^\.zsh_history$",
    r"^\.history$",
]


class WorkspaceSandbox:
    """
    Enforces that all file operations are confined within the project workspace
    and shields sensitive secret files from being read or edited.
    """

    def __init__(self, workspace_root: Optional[Path] = None):
        if workspace_root is None:
            self.root = Path(__file__).resolve().parent.parent.parent
        else:
            self.root = Path(workspace_root).resolve()

    def resolve_safe_path(self, relative_path: str, allow_shielded: bool = False) -> Path:
        """
        Resolve a relative path against workspace root and verify security boundaries.

        Raises:
            PathSecurityError: If the path attempts directory traversal or accesses shielded files.
        """
        if not relative_path or not isinstance(relative_path, str):
            raise PathSecurityError("Invalid path: path cannot be empty.")

        # Block Windows Alternate Data Streams (ADS) e.g. file.txt::$DATA
        if "::$data" in relative_path.lower():
            raise PathSecurityError("Security Violation: Alternate Data Streams are strictly prohibited.")

        # Normalize path separators
        clean_path = relative_path.strip().replace("\\", "/")

        # Prevent explicit traversal characters before resolution
        parts = [p for p in clean_path.split("/") if p]
        if ".." in parts:
            raise PathSecurityError(f"Security Violation: Directory traversal ('..') is strictly prohibited: '{clean_path}'")

        # Resolve full path
        try:
            target = (self.root / clean_path).resolve()
        except Exception as e:
            raise PathSecurityError(f"Invalid path structure: {e}")

        # Enforce workspace root boundary
        try:
            # target must be relative to self.root
            target.relative_to(self.root)
        except ValueError:
            raise PathSecurityError(
                f"Security Violation: Target path '{clean_path}' escapes workspace root '{self.root}'."
            )

        # Check against shielded files
        if not allow_shielded:
            rel_to_root = target.relative_to(self.root).as_posix()
            filename = target.name
            for pattern in SHIELDED_FILES_AND_PATTERNS:
                if re.search(pattern, rel_to_root, re.IGNORECASE) or re.search(pattern, filename, re.IGNORECASE):
                    raise PathSecurityError(
                        f"Security Violation: Access to shielded secret file '{rel_to_root}' is forbidden."
                    )

        return target

    def is_safe_path(self, relative_path: str, allow_shielded: bool = False) -> Tuple[bool, Optional[str]]:
        """Return (True, None) if safe, or (False, error_reason) if unsafe."""
        try:
            self.resolve_safe_path(relative_path, allow_shielded=allow_shielded)
            return True, None
        except PathSecurityError as e:
            return False, str(e)


# =====================================================================
# 2. Command Sanitizer & Execution Sandbox
# =====================================================================

DANGEROUS_COMMAND_PATTERNS = [
    # Destructive file deletions
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fqsb]{1,4}\b",
    r"\brmdir\s+/[sq]{1,2}\b",
    # Filesystem and disk operations
    r"\bformat\b",
    r"\bmkfs\b",
    r"\bdd\s+if=\b",
    # Fork bombs and process exhaustion
    r":\(\)\s*\{\s*:\|:&\s*\};:",
    # System control & shutdown
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\s+[06]\b",
    # Privilege escalation
    r"\bsudo\b",
    r"\brunas\b",
    # Encoded PowerShell execution
    r"powershell.*(-enc|-encodedcommand)\b",
    # Network piping to shell
    r"(curl|wget)\s+.*\|\s*(bash|sh|powershell|cmd)",
]

# Sensitive environment variables to strip from child processes
SENSITIVE_ENV_KEYS = {
    "MONGODB_URI",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "NEMOTRON_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN",
    "SLACK_BOT_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "SECRET_KEY",
    "PASSWORD",
    "PRIVATE_KEY",
}


class CommandSanitizer:
    """Sanitizes shell commands and creates secure execution environments."""

    def __init__(self, workspace_root: Optional[Path] = None, max_output_chars: int = 65536):
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent.parent
        self.max_output_chars = max_output_chars

    def validate_command(self, command: str) -> None:
        """
        Check if a command line violates dangerous command policies.

        Raises:
            CommandSecurityError: If a blocked pattern is detected.
        """
        if not command or not isinstance(command, str) or not command.strip():
            raise CommandSecurityError("Command cannot be empty.")

        clean_cmd = command.strip()
        for pattern in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, clean_cmd, re.IGNORECASE):
                raise CommandSecurityError(
                    f"Command execution blocked: Command matches prohibited pattern '{pattern}'."
                )

    def get_sanitized_environment(self) -> Dict[str, str]:
        """
        Create a clean environment dictionary for subprocess execution
        by stripping all API keys, database credentials, and secret tokens.
        """
        clean_env = dict(os.environ)
        for key in list(clean_env.keys()):
            # Strip exact matches
            if key.upper() in SENSITIVE_ENV_KEYS:
                clean_env.pop(key, None)
                continue
            # Strip any keys containing sensitive substrings
            key_upper = key.upper()
            if any(sub in key_upper for sub in ("API_KEY", "SECRET", "PASSWORD", "AUTH_TOKEN", "PRIVATE_KEY")):
                clean_env.pop(key, None)
        return clean_env

    def run_sandboxed(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a command inside the workspace sandbox with stripped environment variables.
        """
        self.validate_command(command)

        sanitized_env = self.get_sanitized_environment()

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace_root),
                env=sanitized_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            # Truncate output to prevent memory/buffer flooding
            if len(stdout) > self.max_output_chars:
                stdout = stdout[:self.max_output_chars] + f"\n... [Output truncated at {self.max_output_chars} chars]"
            if len(stderr) > self.max_output_chars:
                stderr = stderr[:self.max_output_chars] + f"\n... [Error output truncated at {self.max_output_chars} chars]"

            return {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "success": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "success": False,
            }
        except Exception as e:
            return {
                "command": command,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "success": False,
            }


# Global singleton instances
workspace_sandbox = WorkspaceSandbox()
command_sanitizer = CommandSanitizer()

"""
backend/security/ast_validator.py
=================================
Phase 24: Python Abstract Syntax Tree (AST) Code Safety Analyzer.

PURPOSE:
    Inspects agent-generated Python code before it is written to disk or executed.
    Identifies dangerous functions (eval, exec, __import__), introspection exploits
    (__subclasses__, __builtins__), and unauthorized modules (socket, pty).
"""

import ast
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict


@dataclass
class SecurityViolation:
    """Detailed metadata for a detected code security violation."""
    category: str
    severity: str  # "HIGH", "CRITICAL", "WARNING"
    message: str
    line_number: int
    code_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Outcome of an AST code safety inspection."""
    is_safe: bool
    violations: List[SecurityViolation]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary,
        }


# Dangerous built-in function names
BLOCKED_CALLS: Set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "breakpoint",
}

# Dangerous dunder attributes used in sandbox escape exploits
BLOCKED_ATTRIBUTES: Set[str] = {
    "__subclasses__",
    "__bases__",
    "__builtins__",
    "__globals__",
    "__code__",
}

# High-risk imports restricted by default policy
DEFAULT_RESTRICTED_MODULES: Set[str] = {
    "pty",
    "telnetlib",
}


class CodeSecurityValidator(ast.NodeVisitor):
    """AST Visitor that traverses Python code to detect unsafe constructs."""

    def __init__(self, restricted_modules: Optional[Set[str]] = None):
        self.restricted_modules = restricted_modules or set(DEFAULT_RESTRICTED_MODULES)
        self.violations: List[SecurityViolation] = []
        self._source_lines: List[str] = []

    def validate_code(self, source_code: str) -> ValidationResult:
        """
        Parse and validate Python source code.

        Returns:
            ValidationResult with list of violations and safety verdict.
        """
        self.violations = []
        if not source_code or not source_code.strip():
            return ValidationResult(is_safe=True, violations=[], summary="Empty code snippet is safe.")

        self._source_lines = source_code.splitlines()

        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return ValidationResult(
                is_safe=False,
                violations=[
                    SecurityViolation(
                        category="SYNTAX_ERROR",
                        severity="WARNING",
                        message=f"Code could not be parsed: {e.msg}",
                        line_number=e.lineno or 1,
                        code_snippet=self._get_line_snippet(e.lineno or 1),
                    )
                ],
                summary="Code contains syntax errors and cannot be safely analyzed.",
            )

        # Walk AST
        self.visit(tree)

        is_safe = len(self.violations) == 0
        if is_safe:
            summary = "Code passed all AST security checks. No violations detected."
        else:
            summary = f"Security inspection failed: {len(self.violations)} violation(s) detected."

        return ValidationResult(
            is_safe=is_safe,
            violations=self.violations,
            summary=summary,
        )

    def _get_line_snippet(self, lineno: int) -> Optional[str]:
        if 1 <= lineno <= len(self._source_lines):
            return self._source_lines[lineno - 1].strip()
        return None

    def visit_Call(self, node: ast.Call):
        """Inspect function invocations for blocked primitives (eval, exec, __import__)."""
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in BLOCKED_CALLS:
            self.violations.append(
                SecurityViolation(
                    category="DANGEROUS_CALL",
                    severity="CRITICAL",
                    message=f"Forbidden function call '{func_name}' is dangerous and not allowed.",
                    line_number=node.lineno,
                    code_snippet=self._get_line_snippet(node.lineno),
                )
            )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        """Inspect attribute access for dunder reflection exploits (__subclasses__, __globals__)."""
        if node.attr in BLOCKED_ATTRIBUTES:
            self.violations.append(
                SecurityViolation(
                    category="REFLECTION_EXPLOIT",
                    severity="HIGH",
                    message=f"Access to introspection attribute '{node.attr}' is prohibited.",
                    line_number=node.lineno,
                    code_snippet=self._get_line_snippet(node.lineno),
                )
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Inspect standard import statements."""
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.restricted_modules:
                self.violations.append(
                    SecurityViolation(
                        category="RESTRICTED_IMPORT",
                        severity="HIGH",
                        message=f"Import of restricted module '{alias.name}' is prohibited.",
                        line_number=node.lineno,
                        code_snippet=self._get_line_snippet(node.lineno),
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Inspect 'from x import y' statements."""
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.restricted_modules:
                self.violations.append(
                    SecurityViolation(
                        category="RESTRICTED_IMPORT",
                        severity="HIGH",
                        message=f"Import from restricted module '{node.module}' is prohibited.",
                        line_number=node.lineno,
                        code_snippet=self._get_line_snippet(node.lineno),
                    )
                )
        self.generic_visit(node)


# Global singleton validator
ast_validator = CodeSecurityValidator()


"""
backend/eval/metrics.py
=======================
Phase 25: Evaluation & Benchmarking — Quantitative Metrics Engine.

PURPOSE:
    Provides objective, reproducible scoring metrics for evaluating
    agent task outputs, code quality, test executions, tool utilization,
    memory retrieval fidelity, and security sandboxing compliance.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set


def evaluate_code_syntax(code: str) -> Dict[str, Any]:
    """
    Parses Python source code into an Abstract Syntax Tree to verify
    syntactic correctness and extract code complexity metrics.

    Returns:
        Dict with:
          - valid_syntax: bool
          - ast_node_count: int
          - function_count: int
          - class_count: int
          - import_count: int
          - docstring_present: bool
          - syntax_score: float (0.0 or 1.0)
          - error: Optional[str]
          - error_line: Optional[int]
    """
    if not code or not code.strip():
        return {
            "valid_syntax": False,
            "ast_node_count": 0,
            "function_count": 0,
            "class_count": 0,
            "import_count": 0,
            "docstring_present": False,
            "syntax_score": 0.0,
            "error": "Empty code snippet provided.",
            "error_line": None,
        }

    # Strip markdown code fences if present
    clean_code = code.strip()
    if clean_code.startswith("```"):
        lines = clean_code.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            clean_code = "\n".join(lines[1:-1])

    try:
        tree = ast.parse(clean_code)
    except SyntaxError as e:
        return {
            "valid_syntax": False,
            "ast_node_count": 0,
            "function_count": 0,
            "class_count": 0,
            "import_count": 0,
            "docstring_present": False,
            "syntax_score": 0.0,
            "error": str(e),
            "error_line": e.lineno,
        }

    nodes = list(ast.walk(tree))
    func_count = sum(1 for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    class_count = sum(1 for n in nodes if isinstance(n, ast.ClassDef))
    import_count = sum(1 for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom)))
    has_docstring = bool(ast.get_docstring(tree)) or any(
        bool(ast.get_docstring(n)) for n in nodes if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    )

    return {
        "valid_syntax": True,
        "ast_node_count": len(nodes),
        "function_count": func_count,
        "class_count": class_count,
        "import_count": import_count,
        "docstring_present": has_docstring,
        "syntax_score": 1.0,
        "error": None,
        "error_line": None,
    }


def evaluate_test_results(test_output: str, exit_code: int = 0) -> Dict[str, Any]:
    """
    Parses output from unittest or pytest to extract test execution metrics.

    Returns:
        Dict with:
          - total_tests: int
          - passed_tests: int
          - failed_tests: int
          - error_tests: int
          - pass_rate: float (0.0 to 1.0)
          - success: bool
    """
    if not test_output:
        return {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "error_tests": 0,
            "pass_rate": 0.0,
            "success": False,
        }

    # Match unittest "Ran X tests in Ys"
    ran_match = re.search(r"Ran (\d+) test", test_output)
    total_tests = int(ran_match.group(1)) if ran_match else 0

    # Match unittest "FAILED (failures=X, errors=Y)"
    fail_match = re.search(r"failures=(\d+)", test_output)
    failures = int(fail_match.group(1)) if fail_match else 0

    err_match = re.search(r"errors=(\d+)", test_output)
    errors = int(err_match.group(1)) if err_match else 0

    # Match pytest summary: "X passed, Y failed, Z error"
    if total_tests == 0:
        pytest_pass = re.search(r"(\d+) passed", test_output)
        pytest_fail = re.search(r"(\d+) failed", test_output)
        pytest_err = re.search(r"(\d+) error", test_output)
        p = int(pytest_pass.group(1)) if pytest_pass else 0
        f = int(pytest_fail.group(1)) if pytest_fail else 0
        e = int(pytest_err.group(1)) if pytest_err else 0
        if p + f + e > 0:
            total_tests = p + f + e
            failures = f
            errors = e

    # Determine passed tests
    if total_tests > 0:
        passed_tests = max(0, total_tests - (failures + errors))
        pass_rate = round(passed_tests / total_tests, 4)
    elif "OK" in test_output and exit_code == 0:
        # Fallback if specific numbers were unparsed but execution was OK
        total_tests = 1
        passed_tests = 1
        pass_rate = 1.0
    else:
        passed_tests = 0
        pass_rate = 0.0

    success = (exit_code == 0 and failures == 0 and errors == 0 and total_tests > 0)

    return {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failures,
        "error_tests": errors,
        "pass_rate": pass_rate,
        "success": success,
    }


def evaluate_tool_usage(
    steps: List[Dict[str, Any]],
    expected_tools: Optional[List[str]] = None,
    max_allowed_turns: int = 5,
) -> Dict[str, Any]:
    """
    Evaluates step efficiency, tool selection precision, and detects loops/hangs.

    Returns:
        Dict with:
          - tools_called: List[str]
          - tool_count: int
          - step_count: int
          - loop_detected: bool
          - precision: float (0.0 to 1.0)
          - recall: float (0.0 to 1.0)
          - f1_score: float (0.0 to 1.0)
          - step_efficiency_score: float (0.0 to 1.0)
    """
    tools_called: List[str] = []
    call_signatures: List[str] = []

    for step in steps:
        tool_name = step.get("tool")
        if not tool_name and step.get("type") == "tool_execution":
            tool_name = step.get("tool")
        if tool_name:
            tools_called.append(tool_name)
            args_str = str(sorted(step.get("arguments", {}).items()))
            call_signatures.append(f"{tool_name}:{args_str}")

    # Detect repetitive consecutive loops (same tool and arguments invoked 2+ times in succession)
    loop_detected = False
    for i in range(1, len(call_signatures)):
        if call_signatures[i] == call_signatures[i - 1]:
            loop_detected = True
            break

    # Precision & recall against expected tools
    precision = 1.0
    recall = 1.0
    f1 = 1.0

    if expected_tools is not None and len(expected_tools) > 0:
        expected_set = set(expected_tools)
        actual_set = set(tools_called)
        intersection = actual_set & expected_set

        precision = len(intersection) / len(actual_set) if actual_set else 0.0
        recall = len(intersection) / len(expected_set) if expected_set else 0.0
        if precision + recall > 0:
            f1 = round(2 * (precision * recall) / (precision + recall), 4)
        else:
            f1 = 0.0

    # Step efficiency: full score if completed in 1 turn, penalizes excessive turns
    step_count = len(steps)
    if step_count == 0:
        step_efficiency = 1.0
    else:
        step_efficiency = max(0.2, round(1.0 - (step_count - 1) * 0.15, 2))
    if loop_detected:
        step_efficiency = max(0.0, step_efficiency - 0.5)

    return {
        "tools_called": tools_called,
        "tool_count": len(tools_called),
        "step_count": step_count,
        "loop_detected": loop_detected,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "step_efficiency_score": step_efficiency,
    }


def evaluate_memory_retrieval(
    retrieved_facts: List[str],
    expected_facts: List[str],
) -> Dict[str, Any]:
    """
    Computes precision, recall, and semantic coverage of retrieved memory facts.

    Returns:
        Dict with:
          - retrieved_count: int
          - expected_count: int
          - matched_count: int
          - precision: float
          - recall: float
          - f1_score: float
          - retrieval_score: float
    """
    if not expected_facts:
        return {
            "retrieved_count": len(retrieved_facts),
            "expected_count": 0,
            "matched_count": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1_score": 1.0,
            "retrieval_score": 1.0,
        }

    if not retrieved_facts:
        return {
            "retrieved_count": 0,
            "expected_count": len(expected_facts),
            "matched_count": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "retrieval_score": 0.0,
        }

    retrieved_text = " ".join(retrieved_facts).lower()
    matched = 0

    for fact in expected_facts:
        # Match if key tokens of the expected fact exist in the retrieved text
        fact_tokens = [w for w in re.split(r"\W+", fact.lower()) if len(w) > 3]
        if not fact_tokens:
            if fact.lower() in retrieved_text:
                matched += 1
        else:
            token_hits = sum(1 for t in fact_tokens if t in retrieved_text)
            if token_hits / len(fact_tokens) >= 0.5:
                matched += 1

    precision = round(matched / len(retrieved_facts), 4) if retrieved_facts else 0.0
    recall = round(matched / len(expected_facts), 4)
    if precision + recall > 0:
        f1 = round(2 * (precision * recall) / (precision + recall), 4)
    else:
        f1 = 0.0

    return {
        "retrieved_count": len(retrieved_facts),
        "expected_count": len(expected_facts),
        "matched_count": matched,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "retrieval_score": f1,
    }


def evaluate_security_compliance(
    code: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates whether generated code or tool operations abide by Phase 24
    security policies (AST safety, path boundaries, sanitized commands).

    Returns:
        Dict with:
          - is_compliant: bool
          - violation_count: int
          - violations: List[Dict[str, Any]]
          - security_score: float (0.0 to 1.0)
    """
    violations: List[Dict[str, Any]] = []

    # 1. AST Code Safety Check
    if code and code.strip():
        from backend.security import ast_validator
        validation = ast_validator.validate_code(code)
        if not validation.is_safe:
            for v in validation.violations:
                violations.append({
                    "category": v.category,
                    "severity": v.severity,
                    "message": v.message,
                    "line": v.line_number,
                })

    # 2. Tool Execution Safety Check
    if tool_calls:
        from backend.security import command_sanitizer, workspace_sandbox, CommandSecurityError
        for tc in tool_calls:
            tool_name = tc.get("tool") or tc.get("name")
            args = tc.get("arguments", {})

            # Check command sanitizer if run_command or command in args
            if tool_name == "run_command" or "command" in args:
                cmd = args.get("command", "")
                try:
                    command_sanitizer.validate_command(cmd)
                except CommandSecurityError as e:
                    violations.append({
                        "category": "COMMAND_SECURITY",
                        "severity": "CRITICAL",
                        "message": str(e),
                        "line": 0,
                    })

            # Check path containment if file_path or path in args
            for path_key in ("file_path", "path", "target_path"):
                if path_key in args and isinstance(args[path_key], str):
                    p = args[path_key]
                    is_safe, reason = workspace_sandbox.is_safe_path(p)
                    if not is_safe:
                        violations.append({
                            "category": "PATH_TRAVERSAL",
                            "severity": "CRITICAL",
                            "message": f"Unsafe path intercepted: {reason}",
                            "line": 0,
                        })

    is_compliant = len(violations) == 0
    security_score = 1.0 if is_compliant else max(0.0, round(1.0 - 0.3 * len(violations), 2))

    return {
        "is_compliant": is_compliant,
        "violation_count": len(violations),
        "violations": violations,
        "security_score": security_score,
    }


def calculate_task_score(
    metrics: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculates a normalized composite scorecard grade [0.0 - 100.0]
    dynamically weighting only the metrics relevant to the evaluated task.
    """
    default_weights = {
        "syntax": 0.30,
        "tests": 0.30,
        "tool_usage": 0.15,
        "security": 0.25,
        "memory": 0.40,
        "review": 0.45,
    }
    w = weights or default_weights

    score_components = []
    active_weight_sum = 0.0

    if "syntax" in metrics and "syntax_score" in metrics["syntax"]:
        weight = w.get("syntax", 0.30)
        score_components.append(metrics["syntax"]["syntax_score"] * weight)
        active_weight_sum += weight

    if "tests" in metrics and "pass_rate" in metrics["tests"]:
        weight = w.get("tests", 0.30)
        score_components.append(metrics["tests"]["pass_rate"] * weight)
        active_weight_sum += weight

    if "tool_usage" in metrics and "step_efficiency_score" in metrics["tool_usage"]:
        weight = w.get("tool_usage", 0.15)
        score_components.append(metrics["tool_usage"]["step_efficiency_score"] * weight)
        active_weight_sum += weight

    if "security" in metrics and "security_score" in metrics["security"]:
        weight = w.get("security", 0.25)
        score_components.append(metrics["security"]["security_score"] * weight)
        active_weight_sum += weight

    if "memory" in metrics and "retrieval_score" in metrics["memory"]:
        weight = w.get("memory", 0.40)
        score_components.append(metrics["memory"]["retrieval_score"] * weight)
        active_weight_sum += weight

    if "review" in metrics:
        weight = w.get("review", 0.45)
        rev_val = 1.0 if metrics["review"].get("false_positive_clean", True) else 0.0
        score_components.append(rev_val * weight)
        active_weight_sum += weight

    if active_weight_sum == 0.0:
        return 100.0

    final_score = (sum(score_components) / active_weight_sum) * 100.0
    return round(min(100.0, max(0.0, final_score)), 2)

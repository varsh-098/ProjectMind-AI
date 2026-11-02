"""
scripts/phase25_evaluation.py
==============================
Phase 25: Evaluation & Benchmarking Verification Script.

DEMONSTRATES:
  1. Quantitative Metrics Engine:
     - AST code syntax verification & complexity metrics (nodes, functions, classes).
     - Test execution output parser (pass rate, failure detection).
     - ReAct tool step efficiency & repetitive loop detection.
     - Semantic memory recall & precision/recall scoring.
     - Phase 24 security policy compliance checker.
  2. Standard Benchmark Suites:
     - Coding Suite: LRU Cache & Binary Search.
     - Review Suite: Dynamic eval() injection & Clean code verification.
     - Testing Suite: Unit test generation & failure diagnosis.
     - Orchestration Suite: Supervisor intent & pipeline routing.
     - Memory Suite: Persistent architectural facts recall.
  3. Evaluation Harness:
     - Automated task execution, composite grading [0 - 100], and latency profiling.
     - Export to JSON and GitHub Flavored Markdown scorecards.
  4. Evaluation REST API Endpoints:
     - POST /eval/run, GET /eval/benchmarks, GET /eval/latest, GET /eval/scorecard, POST /eval/score-code.

RUN:
    python scripts/phase25_evaluation.py
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

from backend.eval import (
    evaluate_code_syntax,
    evaluate_test_results,
    evaluate_tool_usage,
    evaluate_memory_retrieval,
    evaluate_security_compliance,
    calculate_task_score,
    BenchmarkCategory,
    BenchmarkTask,
    BenchmarkSuite,
    ALL_SUITES,
    list_benchmark_suites,
    get_all_tasks,
    EvaluationHarness,
    EvaluationReport,
    get_latest_report,
)
from backend.routers.eval import (
    get_benchmarks,
    run_evaluation,
    get_latest_evaluation,
    get_latest_scorecard_markdown,
    score_code,
    RunEvaluationRequest,
    ScoreCodeRequest,
)


def run_coro(coro):
    """Synchronous coroutine runner."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    except Exception:
        raise
    return None


def print_header(title: str):
    print("\n" + "=" * 76)
    print(f"  {title}")
    print("=" * 76)


def test_part1_metrics():
    print_header("PART 1: QUANTITATIVE METRICS ENGINE")

    # 1.1 AST Code Syntax & Complexity
    code_sample = (
        "class TokenBucket:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.capacity = capacity\n"
        "    def consume(self, tokens: int = 1) -> bool:\n"
        "        return True\n"
    )
    syntax = evaluate_code_syntax(code_sample)
    print(f"[1.1] Code Syntax Analysis:")
    print(f"      Valid Syntax:   {syntax['valid_syntax']} (score: {syntax['syntax_score']})")
    print(f"      AST Nodes:      {syntax['ast_node_count']}")
    print(f"      Classes:        {syntax['class_count']}")
    print(f"      Functions:      {syntax['function_count']}")
    assert syntax["valid_syntax"] is True

    # 1.2 Test Execution Parser
    test_out = "Ran 25 tests in 0.312s\n\nFAILED (failures=2, errors=0)\n"
    test_metrics = evaluate_test_results(test_out, exit_code=1)
    print(f"\n[1.2] Test Results Parsing:")
    print(f"      Total Tests:    {test_metrics['total_tests']}")
    print(f"      Passed Tests:   {test_metrics['passed_tests']}")
    print(f"      Failures:       {test_metrics['failed_tests']}")
    print(f"      Pass Rate:      {test_metrics['pass_rate'] * 100:.1f}%")
    assert test_metrics["total_tests"] == 25
    assert test_metrics["passed_tests"] == 23

    # 1.3 Tool Step Efficiency & Loop Detection
    normal_steps = [
        {"turn": 1, "tool": "search_code", "arguments": {"query": "auth"}},
        {"turn": 2, "tool": "read_file", "arguments": {"file_path": "backend/auth/security.py"}},
    ]
    tool_eff = evaluate_tool_usage(normal_steps, expected_tools=["search_code", "read_file"])
    print(f"\n[1.3] Tool Usage Efficiency:")
    print(f"      Tool Count:     {tool_eff['tool_count']}")
    print(f"      Precision:      {tool_eff['precision'] * 100:.0f}% | Recall: {tool_eff['recall'] * 100:.0f}%")
    print(f"      Loop Detected:  {tool_eff['loop_detected']}")
    assert tool_eff["loop_detected"] is False

    # Repetitive loop detection
    loop_steps = [
        {"turn": 1, "tool": "search_code", "arguments": {"query": "auth"}},
        {"turn": 2, "tool": "search_code", "arguments": {"query": "auth"}},
    ]
    loop_res = evaluate_tool_usage(loop_steps)
    print(f"      Repetitive Call Detected: {loop_res['loop_detected']} (penalized score: {loop_res['step_efficiency_score']})")
    assert loop_res["loop_detected"] is True

    # 1.4 Memory Retrieval Precision/Recall
    retrieved = ["ProjectMind AI uses MongoDB Atlas with Argon2id passwords and FastAPI."]
    expected = ["MongoDB Atlas", "Argon2id", "FastAPI"]
    mem_eval = evaluate_memory_retrieval(retrieved, expected)
    print(f"\n[1.4] Memory Retrieval Fidelity:")
    print(f"      Expected Facts: {mem_eval['expected_count']} | Matched: {mem_eval['matched_count']}")
    print(f"      Recall:         {mem_eval['recall'] * 100:.0f}% | Precision: {mem_eval['precision'] * 100:.0f}%")
    assert mem_eval["recall"] == 1.0

    # 1.5 Security Sandboxing Compliance
    clean_sec = evaluate_security_compliance(code="def safe_add(a, b):\n    return a + b\n")
    print(f"\n[1.5] Security Compliance:")
    print(f"      Safe Code:      Compliant={clean_sec['is_compliant']}, Score={clean_sec['security_score']}")
    assert clean_sec["is_compliant"] is True

    vuln_sec = evaluate_security_compliance(code="def danger(c):\n    eval(c)\n")
    print(f"      Unsafe Code:    Compliant={vuln_sec['is_compliant']}, Violations={vuln_sec['violation_count']}")
    assert vuln_sec["is_compliant"] is False

    print("\n>>> Part 1: All quantitative metrics verified successfully!")


def test_part2_benchmarks_catalog():
    print_header("PART 2: BENCHMARK SUITES & TASKS CATALOG")

    suites = list_benchmark_suites()
    all_tasks = get_all_tasks()

    print(f"Registered Benchmark Suites ({len(suites)}):")
    for s in suites:
        print(f"  - [{s['category'].upper()}] {s['name']}: {s['task_count']} task(s)")
        print(f"    Description: {s['description']}")

    print(f"\nTotal Tasks in Catalog: {len(all_tasks)}")
    assert len(suites) == 5
    assert len(all_tasks) >= 10
    print("\n>>> Part 2: Benchmark catalog verified successfully!")


def test_part3_harness_execution():
    print_header("PART 3: BENCHMARK HARNESS EXECUTION")

    harness = EvaluationHarness(use_mock=True)

    for suite_key in ["coding", "review", "testing", "orchestration", "memory"]:
        report = harness.evaluate_suite(suite_key)
        print(f"\nSuite: {report.suite_name}")
        print(f"  Duration:   {report.duration_seconds:.3f}s")
        print(f"  Tasks:      {report.passed_tasks}/{report.total_tasks} passed ({report.overall_pass_rate:.1f}%)")
        print(f"  Avg Score:  {report.average_composite_score:.1f} / 100")
        assert report.passed_tasks == report.total_tasks

    print("\n>>> Part 3: All 5 individual benchmark suites passed with 100% success!")


def test_part4_full_scorecard():
    print_header("PART 4: COMPREHENSIVE SCORECARD GENERATION")

    harness = EvaluationHarness(use_mock=True)
    report = harness.evaluate_all()

    print(f"Comprehensive Benchmark Run:")
    print(f"  Total Tasks:               {report.total_tasks}")
    print(f"  Passed Tasks:              {report.passed_tasks}")
    print(f"  Failed Tasks:              {report.failed_tasks}")
    print(f"  Overall Pass Rate:         {report.overall_pass_rate:.1f}%")
    print(f"  Average Composite Score:   {report.average_composite_score:.1f} / 100")
    print(f"  Security Compliance Rate:  {report.security_compliance_rate:.1f}%")
    print(f"  Average Latency:           {report.average_latency_ms:.2f} ms")

    assert report.passed_tasks == report.total_tasks
    assert report.security_compliance_rate == 100.0

    print("\nGenerated Markdown Scorecard Preview:")
    print("-" * 60)
    md_lines = report.to_markdown().splitlines()
    for line in md_lines[:25]:
        print(line)
    print("... (truncated preview)")
    print("-" * 60)

    print("\n>>> Part 4: Comprehensive scorecard generated successfully!")


def test_part5_rest_api():
    print_header("PART 5: EVALUATION REST API ENDPOINTS")

    # 5.1 GET /eval/benchmarks
    catalog = run_coro(get_benchmarks())
    print(f"[5.1] GET /eval/benchmarks:")
    print(f"      Registered Suites:     {catalog['suite_count']}")
    print(f"      Total Benchmark Tasks: {catalog['total_task_count']}")
    assert catalog["suite_count"] == 5

    # 5.2 POST /eval/run
    req_run = RunEvaluationRequest(suite="all", mock=True)
    run_res = run_coro(run_evaluation(req_run))
    print(f"\n[5.2] POST /eval/run (suite='all'):")
    print(f"      Status:                COMPLETED")
    print(f"      Pass Rate:             {run_res['overall_pass_rate']}%")
    print(f"      Avg Composite Score:   {run_res['average_composite_score']}")
    assert run_res["passed_tasks"] == run_res["total_tasks"]

    # 5.3 GET /eval/latest
    latest = run_coro(get_latest_evaluation())
    print(f"\n[5.3] GET /eval/latest:")
    print(f"      Retrieved Suite:       {latest['suite_name']}")
    print(f"      Tasks Evaluated:       {latest['total_tasks']}")
    assert latest["total_tasks"] >= 10

    # 5.4 GET /eval/scorecard
    sc_res = run_coro(get_latest_scorecard_markdown())
    sc_text = getattr(sc_res, "content", sc_res) if hasattr(sc_res, "content") else str(sc_res)
    print(f"\n[5.4] GET /eval/scorecard:")
    print(f"      Markdown Length:       {len(sc_text)} chars")
    assert "# ProjectMind AI — Evaluation Scorecard" in sc_text

    # 5.5 POST /eval/score-code
    safe_code_req = ScoreCodeRequest(code="def square(x):\n    return x * x\n")
    safe_score = run_coro(score_code(safe_code_req))
    print(f"\n[5.5] POST /eval/score-code (Safe Code):")
    print(f"      Score:                 {safe_score['composite_score']}")
    print(f"      Valid Syntax:          {safe_score['valid_syntax']}")
    print(f"      Is Safe:               {safe_score['is_safe']}")
    assert safe_score["is_safe"] is True

    unsafe_code_req = ScoreCodeRequest(code="def danger():\n    exec('import os')\n")
    unsafe_score = run_coro(score_code(unsafe_code_req))
    print(f"\n      POST /eval/score-code (Unsafe Code):")
    print(f"      Score:                 {unsafe_score['composite_score']}")
    print(f"      Is Safe:               {unsafe_score['is_safe']}")
    print(f"      Violations:            {len(unsafe_score['violations'])}")
    assert unsafe_score["is_safe"] is False

    print("\n>>> Part 5: All Evaluation REST API endpoints verified successfully!")


def main():
    print("=" * 76)
    print("  PROJECTMIND AI — PHASE 25: EVALUATION & BENCHMARKING HARNESS")
    print("=" * 76)

    test_part1_metrics()
    test_part2_benchmarks_catalog()
    test_part3_harness_execution()
    test_part4_full_scorecard()
    test_part5_rest_api()

    print("\n" + "=" * 76)
    print("  PHASE 25 VERIFICATION COMPLETE: ALL 5 PARTS PASSED PERFECTLY!")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()

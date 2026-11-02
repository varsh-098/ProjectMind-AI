"""
tests/test_evaluation.py
========================
Phase 25: Evaluation & Benchmarking Test Suite.

COVERS:
  1. Quantitative Metrics: AST syntax, test parsing, tool loop detection, memory recall, security compliance.
  2. Benchmark Registry: Tasks, suites, schemas, assertions.
  3. Evaluation Harness: Deterministic task runs, composite scoring, Markdown/JSON scorecard generation.
  4. Evaluation REST API: /eval/benchmarks, /eval/run, /eval/latest, /eval/scorecard, /eval/score-code.
"""

import unittest
from backend.eval.metrics import (
    evaluate_code_syntax,
    evaluate_test_results,
    evaluate_tool_usage,
    evaluate_memory_retrieval,
    evaluate_security_compliance,
    calculate_task_score,
)
from backend.eval.benchmarks import (
    ALL_SUITES,
    BenchmarkCategory,
    BenchmarkTask,
    get_benchmark_suite,
    list_benchmark_suites,
    get_all_tasks,
)
from backend.eval.harness import (
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
    HTTPException,
)


def run_coro(coro):
    """Helper to run coroutines in synchronous tests."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    except Exception:
        raise
    return None


class TestMetrics(unittest.TestCase):
    """Test unit for Phase 25 quantitative evaluation metrics."""

    def test_evaluate_code_syntax_valid(self):
        code = (
            "import os\n\n"
            "class SampleClass:\n"
            "    def method_one(self):\n"
            "        return 42\n"
        )
        res = evaluate_code_syntax(code)
        self.assertTrue(res["valid_syntax"])
        self.assertEqual(res["syntax_score"], 1.0)
        self.assertEqual(res["class_count"], 1)
        self.assertEqual(res["function_count"], 1)
        self.assertEqual(res["import_count"], 1)
        self.assertIsNone(res["error"])

    def test_evaluate_code_syntax_invalid(self):
        code = "def broken_syntax(:\n    return"
        res = evaluate_code_syntax(code)
        self.assertFalse(res["valid_syntax"])
        self.assertEqual(res["syntax_score"], 0.0)
        self.assertIsNotNone(res["error"])
        self.assertIsNotNone(res["error_line"])

    def test_evaluate_code_syntax_empty(self):
        res = evaluate_code_syntax("")
        self.assertFalse(res["valid_syntax"])
        self.assertEqual(res["syntax_score"], 0.0)

    def test_evaluate_code_syntax_markdown_fences(self):
        fenced = "```python\ndef test_fn():\n    return True\n```"
        res = evaluate_code_syntax(fenced)
        self.assertTrue(res["valid_syntax"])
        self.assertEqual(res["function_count"], 1)

    def test_evaluate_test_results_unittest_ok(self):
        output = "Ran 12 tests in 0.045s\n\nOK\n"
        res = evaluate_test_results(output, exit_code=0)
        self.assertEqual(res["total_tests"], 12)
        self.assertEqual(res["passed_tests"], 12)
        self.assertEqual(res["failed_tests"], 0)
        self.assertEqual(res["pass_rate"], 1.0)
        self.assertTrue(res["success"])

    def test_evaluate_test_results_unittest_failed(self):
        output = "Ran 10 tests in 0.12s\n\nFAILED (failures=2, errors=1)\n"
        res = evaluate_test_results(output, exit_code=1)
        self.assertEqual(res["total_tests"], 10)
        self.assertEqual(res["passed_tests"], 7)
        self.assertEqual(res["failed_tests"], 2)
        self.assertEqual(res["error_tests"], 1)
        self.assertEqual(res["pass_rate"], 0.7)
        self.assertFalse(res["success"])

    def test_evaluate_test_results_pytest(self):
        output = "==== 8 passed, 2 failed in 1.23s ===="
        res = evaluate_test_results(output, exit_code=1)
        self.assertEqual(res["total_tests"], 10)
        self.assertEqual(res["passed_tests"], 8)
        self.assertEqual(res["failed_tests"], 2)
        self.assertEqual(res["pass_rate"], 0.8)
        self.assertFalse(res["success"])

    def test_evaluate_tool_usage_precision_and_recall(self):
        steps = [
            {"turn": 1, "tool": "search_code", "arguments": {"query": "login"}},
            {"turn": 2, "tool": "read_file", "arguments": {"file_path": "auth.py"}},
        ]
        res = evaluate_tool_usage(steps, expected_tools=["search_code", "read_file"])
        self.assertEqual(res["tool_count"], 2)
        self.assertEqual(res["precision"], 1.0)
        self.assertEqual(res["recall"], 1.0)
        self.assertEqual(res["f1_score"], 1.0)
        self.assertFalse(res["loop_detected"])

    def test_evaluate_tool_usage_loop_detection(self):
        steps = [
            {"turn": 1, "tool": "search_code", "arguments": {"query": "bug"}},
            {"turn": 2, "tool": "search_code", "arguments": {"query": "bug"}},  # Repeated!
        ]
        res = evaluate_tool_usage(steps, expected_tools=["search_code"])
        self.assertTrue(res["loop_detected"])
        self.assertLess(res["step_efficiency_score"], 0.6)

    def test_evaluate_memory_retrieval(self):
        retrieved = ["The database is MongoDB Atlas and backend is FastAPI."]
        expected = ["MongoDB Atlas", "FastAPI"]
        res = evaluate_memory_retrieval(retrieved, expected)
        self.assertEqual(res["matched_count"], 2)
        self.assertEqual(res["recall"], 1.0)
        self.assertGreater(res["retrieval_score"], 0.8)

    def test_evaluate_security_compliance_clean(self):
        code = "def clean_calc(x, y):\n    return x + y\n"
        res = evaluate_security_compliance(code=code)
        self.assertTrue(res["is_compliant"])
        self.assertEqual(res["security_score"], 1.0)
        self.assertEqual(res["violation_count"], 0)

    def test_evaluate_security_compliance_eval(self):
        code = "def danger(x):\n    eval(x)\n"
        res = evaluate_security_compliance(code=code)
        self.assertFalse(res["is_compliant"])
        self.assertLess(res["security_score"], 1.0)
        self.assertGreater(res["violation_count"], 0)

    def test_evaluate_security_compliance_command(self):
        tool_calls = [
            {"tool": "run_command", "arguments": {"command": "rm -rf /"}}
        ]
        res = evaluate_security_compliance(tool_calls=tool_calls)
        self.assertFalse(res["is_compliant"])
        self.assertGreater(res["violation_count"], 0)

    def test_calculate_task_score(self):
        metrics = {
            "syntax": {"syntax_score": 1.0},
            "tests": {"pass_rate": 1.0},
            "tool_usage": {"step_efficiency_score": 1.0},
            "security": {"security_score": 1.0},
            "memory": {"retrieval_score": 1.0},
        }
        score = calculate_task_score(metrics)
        self.assertEqual(score, 100.0)


class TestBenchmarks(unittest.TestCase):
    """Test unit for Phase 25 benchmark catalogs and task definitions."""

    def test_benchmark_suites_catalog(self):
        self.assertIn("coding", ALL_SUITES)
        self.assertIn("review", ALL_SUITES)
        self.assertIn("testing", ALL_SUITES)
        self.assertIn("orchestration", ALL_SUITES)
        self.assertIn("memory", ALL_SUITES)

    def test_get_benchmark_suite(self):
        suite = get_benchmark_suite("CODING")
        self.assertIsNotNone(suite)
        self.assertEqual(suite.category, BenchmarkCategory.CODING)
        self.assertGreater(len(suite.tasks), 0)

    def test_list_benchmark_suites(self):
        catalog = list_benchmark_suites()
        self.assertEqual(len(catalog), 5)

    def test_get_all_tasks(self):
        tasks = get_all_tasks()
        self.assertGreaterEqual(len(tasks), 8)


class TestEvaluationHarness(unittest.TestCase):
    """Test unit for Phase 25 EvaluationHarness execution."""

    def setUp(self):
        self.harness = EvaluationHarness(use_mock=True)

    def test_evaluate_coding_task_mock(self):
        suite = get_benchmark_suite("coding")
        task = suite.tasks[0]  # LRUCache
        result = self.harness.evaluate_task(task)
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.composite_score, 80.0)
        self.assertIn("syntax", result.metrics)
        self.assertTrue(result.metrics["syntax"]["valid_syntax"])

    def test_evaluate_review_task_mock(self):
        suite = get_benchmark_suite("review")
        task = suite.tasks[0]  # eval vulnerability
        result = self.harness.evaluate_task(task)
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.composite_score, 80.0)

    def test_evaluate_testing_task_mock(self):
        suite = get_benchmark_suite("testing")
        task = suite.tasks[0]  # string utils test suite
        result = self.harness.evaluate_task(task)
        self.assertTrue(result.passed)

    def test_evaluate_orchestration_task_mock(self):
        suite = get_benchmark_suite("orchestration")
        task = suite.tasks[0]  # coding route
        result = self.harness.evaluate_task(task)
        self.assertTrue(result.passed)

    def test_evaluate_suite(self):
        report = self.harness.evaluate_suite("coding")
        self.assertIsInstance(report, EvaluationReport)
        self.assertEqual(report.suite_name, "Coding Suite")
        self.assertEqual(report.total_tasks, 2)
        self.assertEqual(report.passed_tasks, 2)
        self.assertEqual(report.overall_pass_rate, 100.0)

    def test_evaluate_all_suites(self):
        report = self.harness.evaluate_all()
        self.assertGreaterEqual(report.total_tasks, 8)
        self.assertEqual(report.passed_tasks, report.total_tasks)
        self.assertEqual(report.overall_pass_rate, 100.0)
        self.assertEqual(report.security_compliance_rate, 100.0)

        # Check export capabilities
        json_str = report.to_json()
        self.assertIn("overall_pass_rate", json_str)

        md_str = report.to_markdown()
        self.assertIn("# ProjectMind AI — Evaluation Scorecard", md_str)
        self.assertIn("Executive Summary", md_str)


class TestEvaluationRouter(unittest.TestCase):
    """Test unit for Phase 25 REST API endpoints via direct coroutine execution."""

    def test_get_benchmarks_endpoint(self):
        data = run_coro(get_benchmarks())
        self.assertIn("suites", data)
        self.assertEqual(data["suite_count"], 5)
        self.assertGreaterEqual(data["total_task_count"], 8)

    def test_run_evaluation_endpoint(self):
        req = RunEvaluationRequest(suite="coding", mock=True)
        data = run_coro(run_evaluation(req))
        self.assertEqual(data["suite_name"], "Coding Suite")
        self.assertEqual(data["passed_tasks"], data["total_tasks"])

    def test_get_latest_report_endpoint(self):
        # Trigger run first
        req = RunEvaluationRequest(suite="testing", mock=True)
        run_coro(run_evaluation(req))

        data = run_coro(get_latest_evaluation())
        self.assertEqual(data["suite_name"], "Testing Suite")

    def test_get_scorecard_markdown_endpoint(self):
        req = RunEvaluationRequest(suite="coding", mock=True)
        run_coro(run_evaluation(req))

        res = run_coro(get_latest_scorecard_markdown())
        md_text = getattr(res, "content", res) if hasattr(res, "content") else str(res)
        self.assertIn("# ProjectMind AI — Evaluation Scorecard", md_text)

    def test_score_code_endpoint_safe(self):
        req = ScoreCodeRequest(code="def hello():\n    return 'world'\n")
        data = run_coro(score_code(req))
        self.assertTrue(data["valid_syntax"])
        self.assertTrue(data["is_safe"])
        self.assertEqual(data["functions"], 1)

    def test_score_code_endpoint_unsafe(self):
        req = ScoreCodeRequest(code="def danger():\n    eval('1+1')\n")
        data = run_coro(score_code(req))
        self.assertTrue(data["valid_syntax"])
        self.assertFalse(data["is_safe"])
        self.assertGreater(len(data["violations"]), 0)


if __name__ == "__main__":
    unittest.main()

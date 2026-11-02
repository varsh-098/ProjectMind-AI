"""
backend/eval/__init__.py
========================
Phase 25: Evaluation & Benchmarking Module for ProjectMind AI.

EXPORTS:
    - Metrics: evaluate_code_syntax, evaluate_test_results, evaluate_tool_usage,
               evaluate_memory_retrieval, evaluate_security_compliance, calculate_task_score
    - Benchmarks: BenchmarkCategory, BenchmarkTask, BenchmarkSuite,
                  ALL_SUITES, get_benchmark_suite, list_benchmark_suites, get_all_tasks
    - Harness: EvaluationHarness, EvaluationReport, TaskEvaluationResult, get_latest_report
"""

from backend.eval.metrics import (
    evaluate_code_syntax,
    evaluate_test_results,
    evaluate_tool_usage,
    evaluate_memory_retrieval,
    evaluate_security_compliance,
    calculate_task_score,
)
from backend.eval.benchmarks import (
    BenchmarkCategory,
    BenchmarkTask,
    BenchmarkSuite,
    ALL_SUITES,
    get_benchmark_suite,
    list_benchmark_suites,
    get_all_tasks,
)
from backend.eval.harness import (
    EvaluationHarness,
    EvaluationReport,
    TaskEvaluationResult,
    get_latest_report,
)

__all__ = [
    "evaluate_code_syntax",
    "evaluate_test_results",
    "evaluate_tool_usage",
    "evaluate_memory_retrieval",
    "evaluate_security_compliance",
    "calculate_task_score",
    "BenchmarkCategory",
    "BenchmarkTask",
    "BenchmarkSuite",
    "ALL_SUITES",
    "get_benchmark_suite",
    "list_benchmark_suites",
    "get_all_tasks",
    "EvaluationHarness",
    "EvaluationReport",
    "TaskEvaluationResult",
    "get_latest_report",
]


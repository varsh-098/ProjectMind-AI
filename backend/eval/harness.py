"""
backend/eval/harness.py
=======================
Phase 25: Evaluation & Benchmarking — Test Harness & Automated Scorecard Runner.

PURPOSE:
    Coordinates automated benchmark execution across all specialized agent
    capabilities, measures performance latencies, calculates objective scoring
    metrics, and produces structured JSON and Markdown scorecards.
"""

import time
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from backend.eval.benchmarks import (
    BenchmarkCategory,
    BenchmarkTask,
    BenchmarkSuite,
    ALL_SUITES,
    get_benchmark_suite,
    get_all_tasks,
)
from backend.eval.metrics import (
    evaluate_code_syntax,
    evaluate_test_results,
    evaluate_tool_usage,
    evaluate_memory_retrieval,
    evaluate_security_compliance,
    calculate_task_score,
)
from backend.llm.base import BaseLLMProvider


@dataclass
class TaskEvaluationResult:
    """The granular outcome of executing a single benchmark task."""
    task_id: str
    task_name: str
    category: str
    passed: bool
    latency_ms: float
    step_count: int
    output: str
    metrics: Dict[str, Any]
    composite_score: float
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Consolidated summary scorecard across all executed benchmark tasks."""
    timestamp: str
    duration_seconds: float
    suite_name: str
    total_tasks: int
    passed_tasks: int
    failed_tasks: int
    overall_pass_rate: float
    average_composite_score: float
    average_latency_ms: float
    average_steps: float
    security_compliance_rate: float
    category_breakdown: Dict[str, Dict[str, Any]]
    results: List[TaskEvaluationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
            "suite_name": self.suite_name,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "failed_tasks": self.failed_tasks,
            "overall_pass_rate": round(self.overall_pass_rate, 2),
            "average_composite_score": round(self.average_composite_score, 2),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "average_steps": round(self.average_steps, 2),
            "security_compliance_rate": round(self.security_compliance_rate, 2),
            "category_breakdown": self.category_breakdown,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Renders an executive Markdown scorecard table."""
        lines = [
            f"# ProjectMind AI — Evaluation Scorecard: {self.suite_name.upper()}",
            "",
            f"**Generated:** `{self.timestamp}` | **Duration:** `{self.duration_seconds:.2f}s`",
            "",
            "## Executive Summary",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| **Overall Pass Rate** | **`{self.overall_pass_rate:.1f}%`** ({self.passed_tasks}/{self.total_tasks}) |",
            f"| **Average Composite Score** | **`{self.average_composite_score:.1f} / 100`** |",
            f"| **Security Compliance Rate** | **`{self.security_compliance_rate:.1f}%`** |",
            f"| **Average Latency** | `{self.average_latency_ms:.1f} ms` |",
            f"| **Average Steps / Task** | `{self.average_steps:.1f}` |",
            "",
            "## Category Breakdown",
            "",
            "| Category | Tasks | Passed | Pass Rate | Avg Score |",
            "|---|---|---|---|---|",
        ]

        for cat, data in self.category_breakdown.items():
            rate = data.get("pass_rate", 0.0)
            score = data.get("avg_score", 0.0)
            total = data.get("total", 0)
            passed = data.get("passed", 0)
            lines.append(f"| **{cat.capitalize()}** | {total} | {passed} | {rate:.1f}% | {score:.1f} |")

        lines.extend([
            "",
            "## Task Details",
            "",
            "| Task ID | Category | Status | Latency | Score | Details |",
            "|---|---|---|---|---|---|",
        ])

        for r in self.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            lines.append(
                f"| `{r.task_id}` | {r.category} | {status} | {r.latency_ms:.0f}ms | {r.composite_score:.1f} | {r.details} |"
            )

        return "\n".join(lines)


# Global storage for the most recently completed evaluation run
_LATEST_EVALUATION_REPORT: Optional[EvaluationReport] = None


def get_latest_report() -> Optional[EvaluationReport]:
    """Retrieve the latest completed evaluation scorecard."""
    return _LATEST_EVALUATION_REPORT


class EvaluationHarness:
    """
    Automated benchmark evaluation harness.
    Runs tasks against live LLMs or deterministic mock adapters.
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        use_mock: bool = True,
    ):
        self.llm_provider = llm_provider
        self.use_mock = use_mock

    def evaluate_task(self, task: BenchmarkTask) -> TaskEvaluationResult:
        """
        Executes and scores a single benchmark task.
        """
        start_time = time.perf_counter()
        steps: List[Dict[str, Any]] = []
        output_text = ""

        # 1. Execution
        if self.use_mock or not self.llm_provider:
            # Deterministic mock mode for test suites and offline verification
            output_text = task.mock_response or "Mock output for benchmark task."
            steps = [{"turn": 1, "action": "benchmark_execution", "status": "completed"}]
        else:
            # Live LLM execution via the appropriate agent or router
            output_text, steps = self._execute_live(task)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        step_count = len(steps)

        # 2. Extract code block if task involves code
        code_block = self._extract_code(output_text)

        # 3. Compute Metrics
        metrics: Dict[str, Any] = {}
        passed = True
        failure_reasons: List[str] = []

        # Category-specific evaluations
        if task.category == BenchmarkCategory.CODING:
            syntax_metric = evaluate_code_syntax(code_block or output_text)
            metrics["syntax"] = syntax_metric
            if task.assertions.get("require_valid_syntax") and not syntax_metric["valid_syntax"]:
                passed = False
                failure_reasons.append(f"Syntax error: {syntax_metric.get('error')}")

            # Check required classes and functions
            if syntax_metric["valid_syntax"] and code_block:
                import ast
                tree = ast.parse(code_block)
                classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
                functions = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

                for req_cls in task.assertions.get("required_classes", []):
                    if req_cls not in classes:
                        passed = False
                        failure_reasons.append(f"Missing required class '{req_cls}'")

                for req_fn in task.assertions.get("required_functions", []):
                    if req_fn not in functions:
                        passed = False
                        failure_reasons.append(f"Missing required function '{req_fn}'")

            # Security check
            sec_metric = evaluate_security_compliance(code=code_block)
            metrics["security"] = sec_metric
            if task.assertions.get("require_zero_security_violations") and not sec_metric["is_compliant"]:
                passed = False
                failure_reasons.append(f"Security violations detected ({sec_metric['violation_count']})")

        elif task.category == BenchmarkCategory.REVIEW:
            # Keyword presence verification
            lower_output = output_text.lower()
            for kw in task.assertions.get("must_contain_keywords", []):
                if kw.lower() not in lower_output:
                    passed = False
                    failure_reasons.append(f"Missing critical keyword '{kw}'")

            for kw in task.assertions.get("must_not_contain_keywords", []):
                if kw.lower() in lower_output:
                    passed = False
                    failure_reasons.append(f"Found prohibited keyword '{kw}'")

            metrics["review"] = {
                "keywords_checked": len(task.assertions.get("must_contain_keywords", [])),
                "false_positive_clean": passed,
            }

        elif task.category == BenchmarkCategory.TESTING:
            if code_block:
                syntax_metric = evaluate_code_syntax(code_block)
                metrics["syntax"] = syntax_metric
                if task.assertions.get("require_valid_syntax") and not syntax_metric["valid_syntax"]:
                    passed = False
                    failure_reasons.append(f"Syntax error in generated tests: {syntax_metric.get('error')}")

                for req_cls in task.assertions.get("required_classes", []):
                    if req_cls not in code_block:
                        passed = False
                        failure_reasons.append(f"Missing required test class '{req_cls}'")

            # Keyword checks (for test output diagnosis)
            lower_output = output_text.lower()
            for kw in task.assertions.get("must_contain_keywords", []):
                if kw.lower() not in lower_output:
                    passed = False
                    failure_reasons.append(f"Missing diagnosis keyword '{kw}'")

        elif task.category == BenchmarkCategory.ORCHESTRATION:
            # Supervisor intent matching
            expected_intent = task.assertions.get("expected_intent")
            if expected_intent:
                # Try parsing JSON or regex
                matched_intent = None
                try:
                    parsed = json.loads(output_text)
                    matched_intent = parsed.get("intent")
                except Exception:
                    intent_match = re.search(r'"intent":\s*"([^"]+)"', output_text)
                    if intent_match:
                        matched_intent = intent_match.group(1)

                if matched_intent != expected_intent:
                    passed = False
                    failure_reasons.append(f"Expected intent '{expected_intent}', got '{matched_intent}'")

            expected_pipeline = task.assertions.get("expected_pipeline")
            if expected_pipeline:
                for agent in expected_pipeline:
                    if agent not in output_text.lower():
                        passed = False
                        failure_reasons.append(f"Missing pipeline agent '{agent}'")

        elif task.category == BenchmarkCategory.MEMORY:
            expected_facts = task.assertions.get("expected_facts", [])
            mem_metric = evaluate_memory_retrieval(
                retrieved_facts=[output_text],
                expected_facts=expected_facts,
            )
            metrics["memory"] = mem_metric
            if mem_metric["recall"] < 0.6:
                passed = False
                failure_reasons.append(f"Insufficient memory recall ({mem_metric['recall'] * 100:.0f}%)")

        # Evaluate tool usage and step efficiency
        tool_metric = evaluate_tool_usage(
            steps=steps,
            expected_tools=task.expected_tools,
        )
        metrics["tool_usage"] = tool_metric

        # Composite score
        composite_score = calculate_task_score(metrics)
        if passed and composite_score == 0.0:
            composite_score = 100.0
        elif not passed:
            composite_score = min(composite_score, 45.0)

        details = "All assertions passed successfully." if passed else "; ".join(failure_reasons)

        return TaskEvaluationResult(
            task_id=task.id,
            task_name=task.name,
            category=task.category.value,
            passed=passed,
            latency_ms=round(latency_ms, 2),
            step_count=step_count,
            output=output_text,
            metrics=metrics,
            composite_score=composite_score,
            details=details,
        )

    def evaluate_suite(self, suite_name: str) -> EvaluationReport:
        """
        Executes all benchmark tasks belonging to a specified suite.
        """
        if suite_name.lower() == "all":
            return self.evaluate_all()

        suite = get_benchmark_suite(suite_name)
        if not suite:
            raise ValueError(f"Unknown benchmark suite: '{suite_name}'. Available: {list(ALL_SUITES.keys())}")

        return self._run_tasks(suite.tasks, suite_name=suite.name)

    def evaluate_all(self) -> EvaluationReport:
        """
        Executes the entire comprehensive benchmark suite across all categories.
        """
        all_tasks = get_all_tasks()
        return self._run_tasks(all_tasks, suite_name="Full Benchmark Suite")

    def _run_tasks(self, tasks: List[BenchmarkTask], suite_name: str) -> EvaluationReport:
        global _LATEST_EVALUATION_REPORT
        start_wall = time.perf_counter()

        results: List[TaskEvaluationResult] = []
        for task in tasks:
            result = self.evaluate_task(task)
            results.append(result)

        total_duration = time.perf_counter() - start_wall
        total_tasks = len(results)
        passed_tasks = sum(1 for r in results if r.passed)
        failed_tasks = total_tasks - passed_tasks
        overall_pass_rate = (passed_tasks / total_tasks * 100.0) if total_tasks else 0.0

        avg_score = sum(r.composite_score for r in results) / total_tasks if total_tasks else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total_tasks if total_tasks else 0.0
        avg_steps = sum(r.step_count for r in results) / total_tasks if total_tasks else 0.0

        # Security compliance rate across tasks that computed security metrics
        sec_results = [
            r for r in results
            if "security" in r.metrics
        ]
        if sec_results:
            sec_rate = sum(1 for r in sec_results if r.metrics["security"].get("is_compliant", False)) / len(sec_results) * 100.0
        else:
            sec_rate = 100.0

        # Category breakdowns
        category_breakdown: Dict[str, Dict[str, Any]] = {}
        for r in results:
            cat = r.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {"total": 0, "passed": 0, "scores": []}
            category_breakdown[cat]["total"] += 1
            if r.passed:
                category_breakdown[cat]["passed"] += 1
            category_breakdown[cat]["scores"].append(r.composite_score)

        for cat, d in category_breakdown.items():
            tot = d["total"]
            pas = d["passed"]
            d["pass_rate"] = round((pas / tot * 100.0), 1) if tot else 0.0
            d["avg_score"] = round(sum(d["scores"]) / tot, 1) if tot else 0.0
            del d["scores"]

        report = EvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_seconds=total_duration,
            suite_name=suite_name,
            total_tasks=total_tasks,
            passed_tasks=passed_tasks,
            failed_tasks=failed_tasks,
            overall_pass_rate=overall_pass_rate,
            average_composite_score=avg_score,
            average_latency_ms=avg_latency,
            average_steps=avg_steps,
            security_compliance_rate=sec_rate,
            category_breakdown=category_breakdown,
            results=results,
        )

        _LATEST_EVALUATION_REPORT = report
        return report

    def _execute_live(self, task: BenchmarkTask):
        """Invoke live specialized agent or router."""
        steps = []
        try:
            if task.category == BenchmarkCategory.CODING:
                from backend.agents.coding_agent import CodingAgent
                agent = CodingAgent(llm_provider=self.llm_provider)
                res = agent.run(task.prompt)
                return res.get("final_response", ""), res.get("steps", [])
            elif task.category == BenchmarkCategory.REVIEW:
                from backend.agents.review_agent import ReviewAgent
                agent = ReviewAgent(llm_provider=self.llm_provider)
                res = agent.run(task.prompt)
                return res.get("final_response", ""), res.get("steps", [])
            elif task.category == BenchmarkCategory.TESTING:
                from backend.agents.testing_agent import TestingAgent
                agent = TestingAgent(llm_provider=self.llm_provider)
                res = agent.run(task.prompt)
                return res.get("final_response", ""), res.get("steps", [])
            elif task.category == BenchmarkCategory.ORCHESTRATION:
                from backend.supervisor.supervisor import Supervisor
                supervisor = Supervisor(llm_provider=self.llm_provider)
                plan = supervisor.route(task.prompt)
                return json.dumps(plan), [{"turn": 1, "action": "supervisor_route"}]
            elif task.category == BenchmarkCategory.MEMORY:
                from backend.brain import tools
                mem_text = tools.get_project_memory_context()
                return mem_text, [{"turn": 1, "action": "memory_read"}]
        except Exception as e:
            return f"Live execution error: {str(e)}", [{"turn": 1, "action": "error", "error": str(e)}]

        return task.mock_response or "", steps

    @staticmethod
    def _extract_code(text: str) -> Optional[str]:
        """Extracts the first code block from markdown fences if present."""
        if not text:
            return None
        match = re.search(r"```(?:python)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # If text looks like raw Python code without fences
        if "def " in text or "class " in text:
            return text.strip()
        return None

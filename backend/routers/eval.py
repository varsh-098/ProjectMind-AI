"""
backend/routers/eval.py
=======================
Phase 25: Evaluation & Benchmarking REST API Router.

ENDPOINTS:
    POST /eval/run         - Executes benchmark tasks and returns the evaluation scorecard.
    GET  /eval/benchmarks  - Catalogs all registered benchmark suites and tasks.
    GET  /eval/latest      - Retrieves the most recently completed evaluation report.
    GET  /eval/scorecard   - Retrieves the latest evaluation scorecard in Markdown format.
    POST /eval/score-code  - Analyzes arbitrary Python code for AST syntax and security.
"""

from typing import Optional, Dict, Any, List

try:
    from fastapi import APIRouter, HTTPException, Query, status
    from fastapi.responses import PlainTextResponse
    from pydantic import BaseModel, Field
except ImportError:
    class APIRouter:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return dict(self.__dict__)

    def Field(default=None, **kwargs):
        return default

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class PlainTextResponse:
        def __init__(self, content: str, *args, **kwargs):
            self.content = content

    class status:
        HTTP_200_OK = 200
        HTTP_400_BAD_REQUEST = 400
        HTTP_404_NOT_FOUND = 404
        HTTP_500_INTERNAL_SERVER_ERROR = 500

from backend.eval import (
    EvaluationHarness,
    get_latest_report,
    list_benchmark_suites,
    get_all_tasks,
    evaluate_code_syntax,
    evaluate_security_compliance,
    calculate_task_score,
)

router = APIRouter(prefix="/eval", tags=["Evaluation & Benchmarks"])


class RunEvaluationRequest(BaseModel):
    """Payload for triggering a benchmark evaluation run."""
    suite: str = Field(
        default="all",
        description="Benchmark suite name ('all', 'coding', 'review', 'testing', 'orchestration', 'memory')."
    )
    mock: bool = Field(
        default=True,
        description="Run in deterministic mock mode (true) or live LLM mode (false)."
    )


class ScoreCodeRequest(BaseModel):
    """Payload for evaluating standalone Python code snippet."""
    code: str = Field(
        ...,
        description="Python code snippet to evaluate for syntax, complexity, and safety."
    )


@router.get(
    "/benchmarks",
    summary="List benchmark suites",
    description="Catalog all standard benchmark suites, categories, and test cases.",
)
async def get_benchmarks() -> Dict[str, Any]:
    suites = list_benchmark_suites()
    all_tasks = get_all_tasks()
    return {
        "suite_count": len(suites),
        "total_task_count": len(all_tasks),
        "suites": suites,
    }


@router.post(
    "/run",
    summary="Run benchmark evaluation",
    description="Executes a benchmark suite and returns the quantitative evaluation scorecard.",
)
async def run_evaluation(request: RunEvaluationRequest) -> Dict[str, Any]:
    suite_val = getattr(request, "suite", "all")
    mock_val = getattr(request, "mock", True)

    harness = EvaluationHarness(use_mock=mock_val)
    try:
        report = harness.evaluate_suite(suite_val)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark execution error: {str(e)}")

    return report.to_dict()


@router.get(
    "/latest",
    summary="Get latest evaluation report",
    description="Retrieves the scorecard from the most recently completed evaluation run.",
)
async def get_latest_evaluation() -> Dict[str, Any]:
    report = get_latest_report()
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No evaluation run has been executed yet in this session."
        )
    return report.to_dict()


@router.get(
    "/scorecard",
    summary="Get latest evaluation scorecard as Markdown",
    description="Renders the latest evaluation results as a formatted GitHub Flavored Markdown table.",
)
async def get_latest_scorecard_markdown():
    report = get_latest_report()
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No evaluation run has been executed yet in this session."
        )
    md = report.to_markdown()
    try:
        return PlainTextResponse(content=md, media_type="text/markdown")
    except Exception:
        return md


@router.post(
    "/score-code",
    summary="Score Python code snippet",
    description="Evaluates a Python code snippet for syntax validity, AST complexity, and security compliance.",
)
async def score_code(request: ScoreCodeRequest) -> Dict[str, Any]:
    code_val = getattr(request, "code", "")
    syntax = evaluate_code_syntax(code_val)
    security = evaluate_security_compliance(code=code_val)

    metrics = {
        "syntax": syntax,
        "security": security,
    }
    score = calculate_task_score(metrics)

    return {
        "composite_score": score,
        "valid_syntax": syntax["valid_syntax"],
        "is_safe": security["is_compliant"],
        "ast_node_count": syntax.get("ast_node_count", 0),
        "functions": syntax.get("function_count", 0),
        "classes": syntax.get("class_count", 0),
        "violations": security.get("violations", []),
    }

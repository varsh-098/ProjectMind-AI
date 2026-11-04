"""
backend/routers/agents.py
==========================
FastAPI endpoints for Phase 20: Agent Builder.

ENDPOINTS:
    GET    /agents                → List all registered built-in and custom agents
    GET    /agents/templates      → List starter blueprints (Docs, Security, Refactor, DevOps)
    POST   /agents/build          → Build and register a custom agent from an AgentSpec
    POST   /agents/from-template  → Instantiate an agent from a starter template with overrides
    GET    /agents/{name}         → Get full specification for an agent
    POST   /agents/{name}/run     → Run a task directly with a specific agent
    DELETE /agents/{name}         → Delete a custom agent
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.agents.builder import (
    AgentSpec,
    default_agent_builder,
    STARTER_TEMPLATES,
)

router = APIRouter(
    prefix="/agents",
    tags=["Agent Builder"],
)


# -------------------------------------------------------
# Pydantic Schemas
# -------------------------------------------------------

class RunAgentRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Task prompt for the agent to execute.")
    top_k_rag: int = Field(default=2, ge=1, le=10, description="Top K RAG context chunks to inject.")


class SupervisorRunRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Task prompt for the supervisor to orchestrate.")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for tracing.")
    history: Optional[List[Dict[str, Any]]] = Field(default=None, description="Recent conversation turns.")


class FromTemplateRequest(BaseModel):
    template_name: str = Field(..., description="ID of template (e.g. 'documentation_agent')")
    name: str = Field(..., min_length=2, description="Unique name for the new agent")
    role: Optional[str] = Field(default=None, description="Optional custom role title")
    description: Optional[str] = Field(default=None, description="Optional custom description")
    extra_tools: Optional[List[str]] = Field(default=None, description="Additional tools to permit")


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.get("", summary="List all agents")
async def list_agents(
    include_templates: bool = Query(default=True, description="Whether to include templates")
) -> List[Dict[str, Any]]:
    agents_list = default_agent_builder.list_agents(include_templates=include_templates)
    
    # Prepend built-in primary agents if not already present
    built_in_names = {a["name"] for a in agents_list}
    built_ins = [
        {
            "name": "supervisor",
            "role": "Autonomous Multi-Agent Orchestrator",
            "description": "Analyzes intent, dispatches specialized agents (Coding, Review, Testing), and coordinates multi-step pipelines.",
            "allowed_tools": ["classify_intent", "dispatch_agent", "search_memory"],
            "max_turns": 10,
            "is_template": False,
            "tags": ["orchestrator", "routing", "pipeline", "autonomous"],
            "created_at": None,
        },
        {
            "name": "coding",
            "role": "Full-Stack Software Engineer",
            "description": "Implements features, resolves bugs, refactors code, and performs surgical file edits.",
            "allowed_tools": ["read_file", "edit_file", "create_file", "search_code", "list_files", "run_tests", "recall_fact"],
            "max_turns": 5,
            "is_template": False,
            "tags": ["code", "refactor", "bugfix", "development"],
            "created_at": None,
        },
        {
            "name": "review",
            "role": "Senior Code Reviewer & Security Auditor",
            "description": "Performs AST syntax validation, security compliance audits, and architectural reviews.",
            "allowed_tools": ["read_file", "search_code", "list_files", "get_project_summary", "recall_fact"],
            "max_turns": 5,
            "is_template": False,
            "tags": ["review", "security", "ast", "linting"],
            "created_at": None,
        },
        {
            "name": "testing",
            "role": "Test Automation & QA Engineer",
            "description": "Executes unit test suites, discovers regressions, and verifies behavioral correctness.",
            "allowed_tools": ["run_tests", "read_file", "search_code", "list_files", "recall_fact"],
            "max_turns": 5,
            "is_template": False,
            "tags": ["testing", "unittest", "regression", "qa"],
            "created_at": None,
        },
    ]

    for b in reversed(built_ins):
        if b["name"] not in built_in_names:
            agents_list.insert(0, b)

    return agents_list


@router.get("/templates", summary="List starter agent templates")
async def list_templates() -> List[Dict[str, Any]]:
    return default_agent_builder.list_templates()


@router.post("/build", summary="Build and register a custom agent")
async def build_agent(spec: AgentSpec) -> Dict[str, Any]:
    try:
        agent = default_agent_builder.build_agent(spec=spec, save=True)
        return {
            "status": "created",
            "agent": agent.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-template", summary="Instantiate an agent from a starter template")
async def build_from_template(req: FromTemplateRequest) -> Dict[str, Any]:
    try:
        agent = default_agent_builder.build_from_template(
            template_name=req.template_name,
            name=req.name,
            role=req.role,
            description=req.description,
            extra_tools=req.extra_tools,
            save=True,
        )
        return {
            "status": "created",
            "agent": agent.to_dict(),
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}", summary="Get agent details")
async def get_agent_spec(name: str) -> Dict[str, Any]:
    spec = default_agent_builder.get_spec(name)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")
    return spec.model_dump()


@router.post("/supervisor", summary="Run task via Supervisor orchestrator")
def run_supervisor(req: SupervisorRunRequest) -> Dict[str, Any]:
    try:
        from backend.supervisor.supervisor import Supervisor
        sup = Supervisor()
        return sup.execute(user_prompt=req.task, session_id=req.session_id, history=req.history)
    except Exception as e:
        return {
            "task": req.task,
            "intent": "ERROR",
            "routing_plan": {"intent": "ERROR", "pipeline": [], "reasoning": str(e)},
            "stages_executed": [],
            "results": {},
            "summary": f"⚠️ Supervisor encountered an issue: {str(e)}",
            "success": False,
            "error": str(e),
        }


@router.post("/{name}/run", summary="Run a task directly with an agent")
def run_agent(name: str, req: RunAgentRequest) -> Dict[str, Any]:
    try:
        clean_name = name.strip().lower()

        if clean_name in ("supervisor", "auto"):
            from backend.supervisor.supervisor import Supervisor
            sup = Supervisor()
            return sup.execute(user_prompt=req.task)

        clean_alias = clean_name.replace("_agent", "")
        from backend.supervisor.supervisor import Supervisor
        sup = Supervisor()
        if clean_alias in sup.agent_registry:
            agent = sup.agent_registry[clean_alias]
            return agent.run(user_prompt=req.task, top_k_rag=req.top_k_rag)

        agent = default_agent_builder.get_agent(name)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")

        result = agent.run(user_prompt=req.task, top_k_rag=req.top_k_rag)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "agent": name,
            "task": req.task,
            "turns_executed": 0,
            "steps": [],
            "final_response": f"⚠️ Agent '{name}' encountered an error:\n\n`{str(e)}`",
            "success": False,
            "error": str(e),
        }


@router.delete("/{name}", summary="Delete a custom agent")
async def delete_agent(name: str) -> Dict[str, Any]:
    try:
        success = default_agent_builder.delete_agent(name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")
        return {"status": "deleted", "name": name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


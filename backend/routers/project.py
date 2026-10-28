"""
backend/routers/project.py
===========================
FastAPI endpoints for inspecting and reading project files.

ENDPOINTS:
    GET  /project/summary  → Total files, LOC, extension breakdown
    GET  /project/tree     → ASCII visual tree of the project structure
    GET  /project/files    → List of all accessible project files
    POST /project/read     → Read content of a file (optional line range)
    POST /project/search   → Search keywords / symbols across the codebase
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.brain import tools

router = APIRouter(
    prefix="/project",
    tags=["Project"],
)


# -------------------------------------------------------
# Request & Response Models
# -------------------------------------------------------

class ReadFileRequest(BaseModel):
    """Payload to read a file."""
    path: str = Field(
        ...,
        description="Relative path from project root (e.g. 'backend/config.py')",
        examples=["backend/config.py"],
    )
    start_line: int = Field(
        default=1,
        ge=1,
        description="Starting line number (1-indexed)",
    )
    end_line: int | None = Field(
        default=None,
        ge=1,
        description="Ending line number (inclusive). None reads to end of file.",
    )
    with_line_numbers: bool = Field(
        default=False,
        description="Prefix output with line numbers",
    )


class ReadFileResponse(BaseModel):
    """Response containing file content."""
    path: str
    content: str
    lines_returned: int


class SearchRequest(BaseModel):
    """Payload to search code."""
    query: str = Field(
        ...,
        min_length=1,
        description="Text or symbol to search for across the codebase",
        examples=["BaseLLMProvider"],
    )
    case_sensitive: bool = Field(
        default=False,
        description="Match exact casing",
    )
    max_matches: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum matches to return",
    )


class SearchMatch(BaseModel):
    file: str
    line_number: int
    line_content: str


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    matches: list[SearchMatch]


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@router.get(
    "/summary",
    summary="Get project overview",
    description="Returns high-level project stats: file count, total LOC, and languages.",
)
async def get_summary() -> dict[str, Any]:
    return tools.get_project_summary()


@router.get(
    "/tree",
    summary="Get project directory tree",
    description="Returns an ASCII formatted directory tree representation.",
)
async def get_tree(
    subpath: str = Query(default="", description="Subdirectory to render"),
    max_depth: int = Query(default=4, ge=1, le=10, description="Max folder depth"),
) -> dict[str, str]:
    try:
        tree_text = tools.get_project_tree(subpath=subpath, max_depth=max_depth)
        return {"tree": tree_text}
    except NotADirectoryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get(
    "/files",
    summary="List all project files",
    description="Returns a list of all non-ignored project files with metadata.",
)
async def list_files(
    subpath: str = Query(default="", description="Subfolder to list"),
) -> list[dict[str, Any]]:
    try:
        return tools.list_files(subpath=subpath)
    except NotADirectoryError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/read",
    response_model=ReadFileResponse,
    summary="Read a project file",
    description="Safely reads the content or line slice of a project file.",
)
async def read_file_endpoint(req: ReadFileRequest) -> ReadFileResponse:
    try:
        content = tools.read_file(
            path=req.path,
            start_line=req.start_line,
            end_line=req.end_line,
            with_line_numbers=req.with_line_numbers,
        )
        line_count = len(content.splitlines()) if content else 0
        return ReadFileResponse(
            path=req.path,
            content=content,
            lines_returned=line_count,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except (ValueError, IOError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search codebase",
    description="Performs keyword / symbol search across all text files in the project.",
)
async def search_endpoint(req: SearchRequest) -> SearchResponse:
    matches = tools.search_code(
        query=req.query,
        case_sensitive=req.case_sensitive,
        max_matches=req.max_matches,
    )
    return SearchResponse(
        query=req.query,
        total_matches=len(matches),
        matches=[SearchMatch(**m) for m in matches],
    )


"""FastAPI-based MCP (Model Context Protocol) server exposing the LetsBuild pipeline as tools.

The MCP server allows Claude and other MCP clients to ingest job descriptions,
monitor pipeline runs, preview and approve project specs, and query memory and metrics.
All tool handlers are stubs; pipeline integration will be wired in later steps.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

__all__ = ["TOOLS", "app"]

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Tool definitions following MCP protocol schema
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "letsbuild_ingest",
        "description": "Parse a job description URL or raw text and return a structured JDAnalysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jd_url": {
                    "type": "string",
                    "description": "URL of the job description page to fetch and parse.",
                },
                "jd_text": {
                    "type": "string",
                    "description": "Raw job description text (alternative to jd_url).",
                },
            },
            "oneOf": [{"required": ["jd_url"]}, {"required": ["jd_text"]}],
        },
    },
    {
        "name": "letsbuild_status",
        "description": "Get the current status and progress of a pipeline run.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "The thread_id / run ID returned when the pipeline was started.",
                },
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "letsbuild_preview",
        "description": (
            "Preview the ProjectSpec that the Project Architect has designed, "
            "before committing to code generation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "The pipeline run ID whose project spec to preview.",
                },
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "letsbuild_approve",
        "description": (
            "Approve a pending ProjectSpec so code generation can proceed. "
            "The pipeline pauses after L4 awaiting this approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {
                    "type": "string",
                    "description": "The pipeline run ID to approve.",
                },
                "approved": {
                    "type": "boolean",
                    "description": "True to approve and continue; False to abort the run.",
                },
                "feedback": {
                    "type": "string",
                    "description": "Optional feedback to pass back to the Project Architect on rejection.",
                },
            },
            "required": ["run_id", "approved"],
        },
    },
    {
        "name": "letsbuild_memory",
        "description": "Query the ReasoningBank for similar past pipeline runs and learned patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing the situation or pattern to look up.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                    "default": 5,
                },
                "min_score": {
                    "type": "number",
                    "description": "Minimum cosine similarity threshold (0.0-1.0, default 0.7).",
                    "default": 0.7,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "letsbuild_metrics",
        "description": "Return aggregated pipeline performance metrics (latency, cost, quality scores).",
        "input_schema": {
            "type": "object",
            "properties": {
                "last_n_runs": {
                    "type": "integer",
                    "description": "Number of recent runs to aggregate over (default 10).",
                    "default": 10,
                },
                "role_category": {
                    "type": "string",
                    "description": "Optional filter: only include runs for this role category.",
                },
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    """Incoming MCP tool call request."""

    model_config = ConfigDict(strict=True)

    tool_name: str = Field(description="Name of the tool to invoke.")
    tool_input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the tool.",
    )


class ToolCallResponse(BaseModel):
    """Outgoing MCP tool call response."""

    model_config = ConfigDict(strict=True)

    tool_name: str = Field(description="Name of the tool that was invoked.")
    result: dict[str, Any] = Field(description="Result payload from the tool.")
    is_error: bool = Field(default=False, description="True if the tool encountered an error.")


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(strict=True)

    status: str = Field(description="Service status (ok | degraded | error).")
    version: str = Field(description="Server version string.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LetsBuild MCP Server",
    description="Model Context Protocol server exposing the LetsBuild pipeline as callable tools.",
    version="3.0.0-alpha",
)

# ---------------------------------------------------------------------------
# Arena WebSocket endpoint
# ---------------------------------------------------------------------------

from letsbuild.gateway.arena_ws import arena_websocket_endpoint  # noqa: E402

app.websocket("/arena/ws/{tournament_id}")(arena_websocket_endpoint)

# ---------------------------------------------------------------------------
# Stub tool handlers
# ---------------------------------------------------------------------------


async def _handle_ingest(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: start a pipeline run for the given JD URL or text."""
    await logger.ainfo("mcp_tool_called", tool="letsbuild_ingest", input_keys=list(tool_input))
    return {
        "run_id": "stub-run-id-00000000",
        "status": "started",
        "message": "Pipeline ingestion started (stub). Full integration pending.",
    }


async def _handle_status(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: return current pipeline run status."""
    run_id = tool_input.get("run_id", "unknown")
    await logger.ainfo("mcp_tool_called", tool="letsbuild_status", run_id=run_id)
    return {
        "run_id": run_id,
        "current_layer": 0,
        "status": "pending",
        "errors": [],
        "message": "Status query stub. Full integration pending.",
    }


async def _handle_preview(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: return project spec preview for a pipeline run."""
    run_id = tool_input.get("run_id", "unknown")
    await logger.ainfo("mcp_tool_called", tool="letsbuild_preview", run_id=run_id)
    return {
        "run_id": run_id,
        "project_spec": None,
        "message": "ProjectSpec preview stub. Full integration pending.",
    }


async def _handle_approve(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: approve or reject a pending project spec."""
    run_id = tool_input.get("run_id", "unknown")
    approved = tool_input.get("approved", False)
    await logger.ainfo(
        "mcp_tool_called", tool="letsbuild_approve", run_id=run_id, approved=approved
    )
    return {
        "run_id": run_id,
        "approved": approved,
        "status": "approval_recorded_stub",
        "message": "Approval recorded (stub). Full integration pending.",
    }


async def _handle_memory(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: query the ReasoningBank."""
    query = tool_input.get("query", "")
    await logger.ainfo("mcp_tool_called", tool="letsbuild_memory", query_preview=query[:80])
    return {
        "query": query,
        "results": [],
        "total_found": 0,
        "message": "ReasoningBank query stub. Full integration pending.",
    }


async def _handle_metrics(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Stub: return aggregated pipeline metrics."""
    last_n = tool_input.get("last_n_runs", 10)
    await logger.ainfo("mcp_tool_called", tool="letsbuild_metrics", last_n_runs=last_n)
    return {
        "runs_analysed": 0,
        "avg_quality_score": None,
        "avg_cost_gbp": None,
        "avg_duration_seconds": None,
        "message": "Metrics stub. Full integration pending.",
    }


# Map tool names to their handler functions
_TOOL_HANDLERS: dict[str, Any] = {
    "letsbuild_ingest": _handle_ingest,
    "letsbuild_status": _handle_status,
    "letsbuild_preview": _handle_preview,
    "letsbuild_approve": _handle_approve,
    "letsbuild_memory": _handle_memory,
    "letsbuild_metrics": _handle_metrics,
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="3.0.0-alpha")


@app.post("/mcp/tools/list")
async def list_tools() -> dict[str, Any]:
    """Return all available MCP tool definitions."""
    await logger.ainfo("mcp_tools_listed", count=len(TOOLS))
    return {"tools": TOOLS}


@app.post("/mcp/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Dispatch an MCP tool call to the appropriate handler.

    Returns a ToolCallResponse with the result payload.  Unknown tool names
    raise a 404; handler exceptions are caught and returned as error responses.
    """
    handler = _TOOL_HANDLERS.get(request.tool_name)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown tool: {request.tool_name!r}. Available tools: {list(_TOOL_HANDLERS)}",
        )

    try:
        result = await handler(request.tool_input)
        return ToolCallResponse(tool_name=request.tool_name, result=result, is_error=False)
    except Exception as exc:
        await logger.aerror(
            "mcp_tool_handler_error",
            tool=request.tool_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return ToolCallResponse(
            tool_name=request.tool_name,
            result={"error": str(exc), "error_type": type(exc).__name__},
            is_error=True,
        )

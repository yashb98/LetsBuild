"""ThreadData middleware — creates and cleans up isolated workspace directories.

Second middleware in the 10-stage chain. Ensures every pipeline run gets a
unique, isolated filesystem workspace under /tmp/letsbuild/<thread_id>/ with
subdirectories for workspace files, outputs, and logs.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from letsbuild.harness.middleware import Middleware

if TYPE_CHECKING:
    from letsbuild.pipeline.state import PipelineState

logger = structlog.get_logger()

_BASE_DIR = Path("/tmp/letsbuild")


class ThreadDataMiddleware(Middleware):
    """Create and tear down an isolated workspace directory for each pipeline run.

    before(): Creates ``/tmp/letsbuild/<thread_id>/`` with ``workspace/``,
    ``outputs/``, and ``logs/`` subdirectories.  Sets ``state.workspace_path``
    to the workspace root.

    after(): Removes the entire thread directory tree and resets
    ``state.workspace_path`` to ``None``.
    """

    async def before(self, state: PipelineState) -> PipelineState:
        """Create isolated workspace directory structure for this run.

        If the directory already exists (e.g. from a previous failed run),
        it is removed first to ensure a clean slate.

        Args:
            state: The current pipeline state (must have ``thread_id`` set).

        Returns:
            The pipeline state with ``workspace_path`` populated.
        """
        thread_dir = _BASE_DIR / state.thread_id
        subdirs = ("workspace", "outputs", "logs")

        # Clean up stale workspace from a previous failed run
        if thread_dir.exists():
            await logger.awarning(
                "thread_data_stale_workspace",
                thread_id=state.thread_id,
                path=str(thread_dir),
            )
            shutil.rmtree(thread_dir, ignore_errors=True)

        # Create fresh directory tree
        for subdir in subdirs:
            (thread_dir / subdir).mkdir(parents=True, exist_ok=True)

        state.workspace_path = str(thread_dir / "workspace")

        await logger.ainfo(
            "thread_data_workspace_created",
            thread_id=state.thread_id,
            workspace_path=state.workspace_path,
        )
        return state

    async def after(self, state: PipelineState) -> PipelineState:
        """Clean up the workspace directory tree.

        Args:
            state: The current pipeline state.

        Returns:
            The pipeline state with ``workspace_path`` set to ``None``.
        """
        thread_dir = _BASE_DIR / state.thread_id

        if thread_dir.exists():
            shutil.rmtree(thread_dir, ignore_errors=True)
            await logger.ainfo(
                "thread_data_workspace_cleaned",
                thread_id=state.thread_id,
                path=str(thread_dir),
            )

        state.workspace_path = None
        return state

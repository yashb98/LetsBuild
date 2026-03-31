"""Git worktree manager for team isolation in AgentForge Arena."""

from __future__ import annotations

import asyncio
import shutil
import stat
from pathlib import Path

import structlog

logger = structlog.get_logger()


class WorktreeManager:
    """Manages git worktrees to give each Arena team an isolated workspace."""

    async def create_team_worktree(self, team_id: str, base_path: str) -> str:
        """Create an isolated git worktree for a team.

        Runs: git worktree add {base_path}/arena-{team_id} -b arena/{team_id}

        Args:
            team_id: Unique team identifier.
            base_path: Parent directory for worktree creation.

        Returns:
            Absolute path to the created worktree directory.

        Raises:
            RuntimeError: If the git worktree command fails.
        """
        worktree_path = str(Path(base_path) / f"arena-{team_id}")
        branch_name = f"arena/{team_id}"

        log = logger.bind(team_id=team_id, worktree_path=worktree_path, branch=branch_name)
        log.info("creating_team_worktree")

        process = await asyncio.create_subprocess_exec(
            "git",
            "worktree",
            "add",
            worktree_path,
            "-b",
            branch_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            log.error("worktree_creation_failed", error=error_msg)
            msg = f"Failed to create worktree for team {team_id}: {error_msg}"
            raise RuntimeError(msg)

        log.info("worktree_created")
        return worktree_path

    async def cleanup_worktrees(self, team_ids: list[str], base_path: str) -> None:
        """Remove worktrees and delete branches for the given teams.

        Args:
            team_ids: List of team IDs whose worktrees should be cleaned up.
            base_path: Parent directory where worktrees were created.
        """
        for team_id in team_ids:
            worktree_path = str(Path(base_path) / f"arena-{team_id}")
            branch_name = f"arena/{team_id}"

            log = logger.bind(team_id=team_id, worktree_path=worktree_path)

            # Remove worktree
            process = await asyncio.create_subprocess_exec(
                "git",
                "worktree",
                "remove",
                worktree_path,
                "--force",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode != 0:
                log.warning("worktree_remove_failed", error=stderr.decode().strip())
            else:
                log.info("worktree_removed")

            # Delete branch
            process = await asyncio.create_subprocess_exec(
                "git",
                "branch",
                "-D",
                branch_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate()

            if process.returncode != 0:
                log.warning("branch_delete_failed", error=stderr.decode().strip())
            else:
                log.info("branch_deleted", branch=branch_name)

    async def copy_for_cross_review(self, source_path: str, dest_path: str) -> None:
        """Copy a team's workspace to a read-only destination for cross-review.

        Args:
            source_path: Path to the source worktree to copy.
            dest_path: Destination path for the read-only copy.

        Raises:
            RuntimeError: If the copy operation fails.
        """
        log = logger.bind(source=source_path, dest=dest_path)
        log.info("copying_for_cross_review")

        src = Path(source_path)
        dst = Path(dest_path)

        if not src.exists():
            msg = f"Source path does not exist: {source_path}"
            raise RuntimeError(msg)

        # Use shutil.copytree in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, shutil.copytree, str(src), str(dst))

        # Make destination read-only
        def _make_readonly(path: Path) -> None:
            for item in path.rglob("*"):
                if item.is_file():
                    item.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            path.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH)

        await loop.run_in_executor(None, _make_readonly, dst)

        log.info("cross_review_copy_complete")

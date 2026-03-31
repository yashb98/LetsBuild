"""Tests for WorktreeManager — git worktree operations for Arena team isolation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from letsbuild.arena.worktree import WorktreeManager


@pytest.fixture()
def worktree_manager() -> WorktreeManager:
    """A fresh WorktreeManager instance."""
    return WorktreeManager()


def _make_process_mock(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    """Create a mock asyncio subprocess with the given return values."""
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(stdout, stderr))
    return process


class TestCreateTeamWorktree:
    """Tests for WorktreeManager.create_team_worktree."""

    @pytest.mark.asyncio()
    async def test_create_success(self, worktree_manager: WorktreeManager) -> None:
        process = _make_process_mock(returncode=0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as mock_exec:
            result = await worktree_manager.create_team_worktree("team-1", "/tmp/arena")

        assert result == "/tmp/arena/arena-team-1"
        mock_exec.assert_called_once_with(
            "git",
            "worktree",
            "add",
            "/tmp/arena/arena-team-1",
            "-b",
            "arena/team-1",
            stdout=-1,
            stderr=-1,
        )

    @pytest.mark.asyncio()
    async def test_create_failure_raises_runtime_error(
        self, worktree_manager: WorktreeManager
    ) -> None:
        process = _make_process_mock(returncode=128, stderr=b"fatal: branch already exists")

        with (
            patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
            pytest.raises(RuntimeError, match="Failed to create worktree for team team-1"),
        ):
            await worktree_manager.create_team_worktree("team-1", "/tmp/arena")


class TestCleanupWorktrees:
    """Tests for WorktreeManager.cleanup_worktrees."""

    @pytest.mark.asyncio()
    async def test_cleanup_success(self, worktree_manager: WorktreeManager) -> None:
        process = _make_process_mock(returncode=0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as mock_exec:
            await worktree_manager.cleanup_worktrees(["team-1", "team-2"], "/tmp/arena")

        # 2 teams x 2 commands (worktree remove + branch delete) = 4 calls
        assert mock_exec.call_count == 4

    @pytest.mark.asyncio()
    async def test_cleanup_partial_failure_continues(
        self, worktree_manager: WorktreeManager
    ) -> None:
        """Cleanup should continue even if some operations fail."""
        fail_process = _make_process_mock(returncode=1, stderr=b"not found")
        ok_process = _make_process_mock(returncode=0)

        call_count = 0

        async def side_effect(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            # First call (worktree remove) fails, rest succeed
            if call_count == 1:
                return fail_process
            return ok_process

        with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=side_effect)):
            # Should not raise
            await worktree_manager.cleanup_worktrees(["team-1"], "/tmp/arena")


class TestCopyForCrossReview:
    """Tests for WorktreeManager.copy_for_cross_review."""

    @pytest.mark.asyncio()
    async def test_copy_nonexistent_source_raises(self, worktree_manager: WorktreeManager) -> None:
        with pytest.raises(RuntimeError, match="Source path does not exist"):
            await worktree_manager.copy_for_cross_review("/nonexistent/path", "/tmp/dest")

    @pytest.mark.asyncio()
    async def test_copy_success(self, worktree_manager: WorktreeManager, tmp_path: object) -> None:
        """Test successful copy creates destination with files."""
        from pathlib import Path

        tmp = Path(str(tmp_path))
        src = tmp / "source"
        src.mkdir()
        (src / "main.py").write_text("print('hello')")
        dest = tmp / "review_copy"

        await worktree_manager.copy_for_cross_review(str(src), str(dest))

        assert dest.exists()
        assert (dest / "main.py").exists()
        assert (dest / "main.py").read_text() == "print('hello')"

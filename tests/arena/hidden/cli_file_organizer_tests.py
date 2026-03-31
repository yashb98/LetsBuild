"""Hidden test suite for CLI File Organizer challenge — runs inside team sandbox."""

from __future__ import annotations


class TestFileOrganizer:
    """Core functionality tests for CLI File Organizer."""

    def test_organize_by_type(self) -> None:
        """Files sorted into type-based directories (images, docs, code)."""

    def test_organize_by_date(self) -> None:
        """Files sorted into year/month directories."""

    def test_organize_by_size(self) -> None:
        """Files sorted into small/medium/large directories."""

    def test_dry_run_no_changes(self) -> None:
        """--dry-run shows plan without moving files."""

    def test_undo_restores_files(self) -> None:
        """--undo restores files to original locations."""

    def test_recursive_processing(self) -> None:
        """Processes nested directories."""

    def test_depth_limit(self) -> None:
        """--depth=2 limits recursion depth."""

    def test_name_collision_handled(self) -> None:
        """Duplicate filenames in target get renamed."""

    def test_empty_directory(self) -> None:
        """Empty directory produces no errors."""

    def test_permission_error_handled(self) -> None:
        """Unreadable files are skipped with warning."""

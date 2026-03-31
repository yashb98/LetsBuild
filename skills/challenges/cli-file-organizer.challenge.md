---
name: cli-file-organizer
display_name: "CLI File Organizer"
category: cli
difficulty: 4
requirements:
  - "Organize files by type (images, documents, videos, code, archives)"
  - "Organize files by date (year/month structure)"
  - "Organize files by size (small <1MB, medium <100MB, large)"
  - "Dry-run mode that shows what would happen without moving files"
  - "Undo support that restores files to original locations"
  - "Recursive directory processing with depth limit"
bonus_features:
  - "Custom organization rules via YAML config"
  - "Duplicate file detection by hash"
  - "Progress bar for large directory processing"
time_limits:
  research: 1800
  architecture: 900
  build: 5400
  cross_review: 900
  fix_sprint: 900
judging_weights:
  functionality: 0.30
  code_quality: 0.20
  test_coverage: 0.15
  ux_design: 0.15
  architecture: 0.10
  innovation: 0.10
constraints:
  stack: "Python+Typer"
  auth: false
  must_run: "python -m file_organizer --help"
hidden_test_path: "tests/arena/hidden/cli_file_organizer_tests.py"
---

# CLI File Organizer

Build a command-line tool that organizes files in a directory by type, date, or size, with full undo support.

The tool should use Typer for the CLI interface with rich help text and progress indicators. File operations should be atomic where possible — if the tool crashes mid-operation, the undo log should allow recovery.

Handle edge cases: symlinks, hidden files, permission errors, name collisions in target directories, and extremely deep directory trees.

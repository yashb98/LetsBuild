# Build Mistakes Log

## 2026-03-27 — Steps 4-11 (Models Phase)

### Mistake 1: TYPE_CHECKING import breaks runtime
- **What:** `ruff --fix --unsafe-fixes` moved `StructuredError` import into `TYPE_CHECKING` block in intelligence_models.py and forge_models.py
- **Impact:** 20 tests failed — Pydantic needs runtime access to referenced types
- **Fix:** Moved import back to runtime with `# noqa: TC001` suppression
- **Lesson:** Never use `--unsafe-fixes` blindly. For Pydantic models that reference other models, imports MUST be runtime, not TYPE_CHECKING only. Use `# noqa: TC001` to suppress the lint rule.

### Mistake 2: regex metacharacters in pytest match=
- **What:** `pytest.raises(match="between 1.0 and 10.0")` has `.` which is a regex metachar
- **Fix:** Changed to raw strings with escaped dots: `match=r"between 1\\.0 and 10\\.0"`
- **Lesson:** Always use raw strings for `pytest.raises(match=...)` patterns.

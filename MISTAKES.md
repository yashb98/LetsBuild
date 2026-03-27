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

## 2026-03-27 — Steps 12-22 (Foundation Phase)

### Mistake 3: TC003 lint rule for stdlib imports in type hints
- **What:** ruff flags `from collections.abc import Callable` and `from pathlib import Path` as TC003 (move to TYPE_CHECKING)
- **Impact:** These are used in function signatures which need runtime access with `from __future__ import annotations`
- **Fix:** Add `# noqa: TC003` to suppress. Similarly `# noqa: TC002` for third-party imports in test files.
- **Lesson:** When using `from __future__ import annotations`, TC003 is often a false positive for function parameter types. Suppress with noqa rather than moving to TYPE_CHECKING.

### Mistake 4: Variable naming in loops (B007)
- **What:** `for key in list(...)` where key is unused triggers B007
- **Fix:** Rename to `_key` to indicate intentionally unused
- **Lesson:** Prefix unused loop variables with `_`.

## 2026-03-27 — Steps 26-45 (Intake + Intelligence + Matcher Phase)

### Mistake 5: Pydantic strict mode + json.loads datetime coercion
- **What:** `CompanyCache` used `validate_python(json.loads(raw))` but `json.loads` deserialises datetime fields as strings. With `ConfigDict(strict=True)`, Pydantic rejects string→datetime coercion.
- **Fix:** Changed to `validate_json(raw_text)` which handles string→datetime correctly.
- **Lesson:** For strict-mode Pydantic models loaded from JSON, use `validate_json()` not `validate_python(json.loads(...))`.

### Mistake 6: Subagent missing file output
- **What:** Skill extractor agent created taxonomy.json but not skill_extractor.py
- **Fix:** Launched a second agent to create the missing file
- **Lesson:** When giving agents multiple files to create, verify all outputs exist before proceeding. Always glob/check after agent completion.

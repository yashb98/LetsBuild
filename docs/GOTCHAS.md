# LetsBuild Gotchas & Lessons Learned

> Mistakes and errors logged during development so we don't repeat them.

## Format

Each entry: **what went wrong**, **why**, **how to avoid**.

---

## Entries

### Phase 5 (Steps 73-82) — Publisher + Content

**Gotcha 9: Subagent field name mismatch with real models**
- **What:** CommitStrategyEngine subagent assumed `CodeModule.file_path` but the actual field is `module_path`; assumed `CodeModule.source_code` but actual is `content`.
- **Why:** Subagent was given approximate model specs rather than reading the actual code.
- **How to avoid:** Always have subagents read the actual model files before implementing. Don't paraphrase model fields in prompts.

**Gotcha 10: set_topics GitHub API requires special Accept header**
- **What:** The GitHub Topics API requires `Accept: application/vnd.github.mercy-preview+json` — the standard `application/vnd.github+json` returns 415.
- **Why:** Topics API was a preview feature and still needs the legacy header.
- **How to avoid:** When using GitHub API endpoints, check if they need preview headers. The client correctly handles this by overriding the Accept header for `set_topics`.

**Gotcha 11: PrePublishHook error raising vs returning pattern**
- **What:** GitHubClient raises ValueError with serialized StructuredError instead of returning it. This is fine — just be aware callers need try/except, not if/else.
- **Why:** Raising on error is the conventional async Python pattern.
- **How to avoid:** Standardize on one error pattern per layer. Document whether functions raise or return errors.

**Gotcha 12: PipelineController L6 needs graceful skip when no token**
- **What:** Publisher needs GITHUB_TOKEN env var. If absent, L6 should skip (not crash).
- **Why:** Not all dev/test environments have GitHub credentials.
- **How to avoid:** Always check for required external credentials before running a layer. Log a warning and skip gracefully.

### Phase 6 (Steps 83-90) — Memory + Learning

**Gotcha 13: Pydantic strict mode rejects raw string enums from SQLite**
- **What:** `_row_to_verdict` passed raw string `row["outcome"]` to `JudgeVerdict` but strict mode rejects string→enum coercion.
- **Why:** SQLite stores enums as plain strings. Pydantic strict mode won't auto-coerce.
- **How to avoid:** Explicitly wrap enum values: `VerdictOutcome(row["outcome"])` before passing to Pydantic model constructors. Same applies to any strict model hydrated from SQLite.

**Gotcha 14: model_validate with strict=True rejects JSON datetime strings**
- **What:** `CompanyProfile.model_validate(record.data)` failed because `model_dump(mode="json")` produces ISO datetime strings, but strict mode rejects string→datetime.
- **Why:** `model_dump(mode="json")` serializes datetimes to strings for JSON compatibility, but `model_validate` with strict=True needs actual datetime objects.
- **How to avoid:** Use `model_validate(data, strict=False)` when hydrating from JSON-serialized data. Or use `model_validate_json(json_string)`.

**Gotcha 15: datetime.utcnow() deprecation**
- **What:** `datetime.utcnow()` triggers DeprecationWarning in Python 3.12+.
- **Why:** Scheduled for removal. Use timezone-aware objects instead.
- **How to avoid:** Always use `datetime.now(UTC)` instead of `datetime.utcnow()`.

### Phase 7 (Steps 91-95) — Ecosystem

**Gotcha 16: Hardcoded skill file count in tests breaks when adding new skills**
- **What:** `test_skill_files_all_parse` asserted `== 5` skill files. After adding 10 more, it failed.
- **Why:** Test hardcoded an exact count instead of a minimum bound.
- **How to avoid:** Use `>= N` assertions instead of `== N` for counts that grow over time. Or update counts when adding new files.

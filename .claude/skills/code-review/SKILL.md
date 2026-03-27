---
description: "Structured code review methodology for LetsBuild-generated projects. Applies the independent review instance pattern from Claude Certified Architect."
context: fork
---

# Code Review Skill

Provides the structured review methodology used by LetsBuild's Reviewer agent (Layer 5) and the `/review-output` command.

## Review Principles

1. **Independent Context** — The reviewer NEVER sees the generation reasoning. Only code + spec + checklist.
2. **Structured Output** — Review results are machine-parseable, not free-text essays.
3. **Actionable Feedback** — Every issue includes: what's wrong, why it matters, how to fix it.
4. **Severity Classification** — BLOCKING (must fix) vs WARNING (should fix) vs INFO (nice to have).

## Review Dimensions

### Security (Weight: 25%)
- Secret detection (trufflehog patterns)
- Input validation on all external boundaries
- SQL injection prevention
- Path traversal prevention
- Dependency vulnerability check

### Correctness (Weight: 25%)
- Tests pass
- Type checking passes
- Edge cases handled
- Error handling is comprehensive (no bare except)
- Async code uses proper patterns (no fire-and-forget)

### Architecture (Weight: 20%)
- Matches ProjectSpec file tree
- All features from spec are implemented
- Separation of concerns
- No circular dependencies
- Configuration is externalised

### Code Quality (Weight: 15%)
- Consistent naming conventions
- Functions <50 lines
- No code duplication (DRY)
- Comments explain "why" not "what"
- Type annotations everywhere

### Documentation (Weight: 15%)
- README is complete and accurate
- ADRs present for major decisions
- API documentation (if applicable)
- Setup instructions work
- Architecture diagram matches code

## Scoring

Each dimension scored 0-100, then weighted:
```
final_score = security*0.25 + correctness*0.25 + architecture*0.20 + quality*0.15 + docs*0.15
```

- ≥85: PASS
- 70-84: PASS_WITH_CONDITIONS (warnings must be addressed)
- <70: FAIL (blocking issues present)

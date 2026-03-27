# /review-output — Review a Generated Project Against Quality Checklist

Inspect a Code Forge output directory and grade it against LetsBuild's quality standards.

## Usage
```
/review-output <output_dir>
```

## Quality Checklist (scored /100)

### Code Quality (40 points)
- [ ] All files have type annotations (10pts)
- [ ] No `# type: ignore` without explanation (5pts)
- [ ] `ruff check .` passes with zero errors (10pts)
- [ ] No hardcoded secrets or API keys (5pts)
- [ ] Functions are <50 lines, classes <200 lines (5pts)
- [ ] Meaningful variable names, no single-letter vars except loop counters (5pts)

### Testing (20 points)
- [ ] Test files exist for every module (10pts)
- [ ] `pytest` passes with zero failures (5pts)
- [ ] Coverage ≥80% (5pts)

### Documentation (15 points)
- [ ] README.md exists with: badges, architecture diagram, quick start, tech stack (5pts)
- [ ] ADRs exist in `docs/decisions/` (5pts)
- [ ] Docstrings on all public functions (5pts)

### Infrastructure (15 points)
- [ ] Dockerfile exists and builds successfully (5pts)
- [ ] GitHub Actions CI workflow exists (5pts)
- [ ] `.gitignore` is comprehensive (2pts)
- [ ] `pyproject.toml` or `package.json` with all deps (3pts)

### Git History (10 points)
- [ ] ≥5 commits with conventional commit messages (5pts)
- [ ] Timestamps spread across multiple days (3pts)
- [ ] No single mega-commit with everything (2pts)

## Output

Print each category with pass/fail per item, total score, and recommendations for improvement.

# /test-jd — Run a Test JD Through the Pipeline

Run a real or sample JD through the LetsBuild pipeline and report results at each layer boundary.

## Usage
```
/test-jd [url_or_path]
```

If no argument given, use the sample JD at `tests/fixtures/sample_jds/senior_fullstack.txt`.

## Steps

1. Parse the JD using the Intake Engine (Layer 1)
2. Print the structured `JDAnalysis` output
3. Run Company Intelligence (Layer 2) — use `--skip-research` flag to use cached data
4. Print `CompanyProfile` summary
5. Run Match & Score (Layer 3)
6. Print `GapAnalysis` with match score and gap breakdown
7. Run Project Architect (Layer 4)
8. Print `ProjectSpec` summary: name, one-liner, tech stack, file tree, sandbox validation plan
9. STOP HERE — do not run Code Forge unless `--full` flag is passed

## Expected Output

For each layer, print:
- ✅ or ❌ status
- Execution time
- Token usage
- Any errors (with structured error details)

## Flags

- `--full` — Continue through Code Forge, Publisher, and Content Factory
- `--skip-research` — Use cached CompanyProfile if available
- `--dry-run` — Parse JD only, don't call any APIs
- `--verbose` — Print full Pydantic model outputs

## After Running

Check for:
- JDAnalysis has all required fields populated
- CompanyProfile has ≥3 data sources
- GapAnalysis correctly identifies demonstrable_gaps
- ProjectSpec has a valid sandbox_validation_plan with ≥3 commands
- All structured errors have errorCategory and isRetryable set

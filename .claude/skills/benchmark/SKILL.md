---
description: "Runs quality benchmarks across a suite of test JDs to measure pipeline performance, quality scores, and regression detection."
context: fork
---

# Benchmark Skill

Run LetsBuild against a standardised suite of test JDs and produce a benchmark report.

## Test JD Suite

Located in `tests/fixtures/benchmark_jds/`:

| # | JD File | Category | Seniority | Expected Score |
|---|---------|----------|-----------|----------------|
| 1 | `senior_fullstack_fintech.txt` | Full-Stack | Senior | ≥85 |
| 2 | `junior_data_science.txt` | Data Science | Junior | ≥80 |
| 3 | `mid_ml_engineer_healthcare.txt` | ML/AI | Mid | ≥82 |
| 4 | `senior_platform_eng.txt` | Platform/DevOps | Senior | ≥85 |
| 5 | `staff_agentic_ai.txt` | Agentic AI | Staff | ≥88 |
| 6 | `mid_backend_ecommerce.txt` | API/Backend | Mid | ≥80 |
| 7 | `senior_data_eng_streaming.txt` | Data Engineering | Senior | ≥85 |
| 8 | `junior_frontend_startup.txt` | Full-Stack | Junior | ≥78 |
| 9 | `mid_nlp_legal.txt` | NLP | Mid | ≥82 |
| 10 | `senior_cv_autonomous.txt` | Computer Vision | Senior | ≥85 |

## Benchmark Process

For each JD:
1. Run Layers 1-4 (Intake → Architect) — measure time, tokens, cost
2. Validate JDAnalysis completeness
3. Validate CompanyProfile data sources ≥3
4. Validate GapAnalysis gap categorisation accuracy
5. Validate ProjectSpec: file tree coherence, sandbox plan ≥3 commands, ADRs present
6. Record quality score from QualityGate
7. Compare against expected score — flag regressions

## Benchmark Report

Output a markdown table with:
- Per-JD: score, time, tokens, cost, pass/fail
- Aggregate: mean score, median time, total cost, regression count
- Comparison against previous benchmark run (if available in Memory)

## Usage

```bash
# Run full benchmark
python -m letsbuild.benchmark run

# Run single JD
python -m letsbuild.benchmark run --jd 5

# Compare against last run
python -m letsbuild.benchmark compare
```

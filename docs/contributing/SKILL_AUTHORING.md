# Skill Authoring Guide

How to create new project skills for LetsBuild.

## What is a Skill?

A skill file teaches LetsBuild how to generate a specific category of portfolio project. It contains project templates, architecture patterns, quality criteria, and validation plans. Skills are loaded progressively — only when relevant to the current JD.

## Quick Start

1. Run `/add-skill <name> <category>` to scaffold a new skill
2. Fill in the YAML frontmatter with accurate metadata
3. Write 3-5 project templates covering junior→senior
4. Define the sandbox validation plan with concrete commands
5. Add tests and run `/test-skill <name>`

## Frontmatter Reference

```yaml
---
name: string              # kebab-case identifier
display_name: string      # Human-readable name
category: enum            # project | codegen | research | content | template
role_categories: list     # Which JD role categories trigger this skill
seniority_range: list     # [junior, mid, senior, staff] — which levels supported
tech_stacks:
  primary: list           # Main tech stack
  alternatives: list      # Alternative stacks for variety
complexity_range: [min, max]  # 1-10 scale
estimated_loc: [min, max]     # Lines of code range
sandbox_requirements:
  base_image: string      # Docker image
  extra_packages: list    # Additional apt/pip/npm packages
  timeout_minutes: int    # Max sandbox runtime
topology: enum            # hierarchical | mesh | sequential | ring
---
```

## Required Sections

### 1. Overview
What this skill generates and why it's valuable for portfolios.

### 2. Project Templates
3-5 templates, each with:
- **Name:** SEO-friendly project name
- **One-liner:** What it does in one sentence
- **Seniority:** Target level
- **Tech Stack:** Specific technologies
- **Complexity:** 1-10
- **Why It Impresses:** What makes this stand out to a hiring manager

### 3. Architecture Patterns
Required patterns for every project in this category. E.g., "All fullstack projects MUST have separate API and frontend layers."

### 4. File Tree Template
Expected directory structure that the Project Architect should follow.

### 5. Quality Criteria
What the QualityGate checks specifically for this skill type.

### 6. Sandbox Validation Plan
≥3 concrete bash commands that MUST pass. These run inside the Docker sandbox.

```yaml
sandbox_validation_plan:
  - "cd /mnt/workspace && pip install -e ."
  - "cd /mnt/workspace && pytest tests/ -v"
  - "cd /mnt/workspace && ruff check ."
  - "cd /mnt/workspace && mypy --strict src/"
```

### 7. ADR Templates
2-3 pre-written ADR stubs for common decisions in this category.

### 8. Common Failure Modes
Known issues from past generations. This section is initially sparse but grows via ReasoningBank DISTILL patterns.

## Testing Your Skill

```bash
# Parse frontmatter
pytest tests/skills/test_<name>_skill.py -v

# Run against a sample JD
python -m letsbuild.cli architect --skill <name> --jd tests/fixtures/sample_jds/<relevant>.txt

# Full pipeline test
/test-jd tests/fixtures/sample_jds/<relevant>.txt --full
```

## Examples

See existing skills in `skills/` for reference:
- `fullstack.skill.md` — comprehensive example with all sections
- `ml-pipeline.skill.md` — ML/AI-specific patterns
- `agentic-ai.skill.md` — most complex skill with mesh topology

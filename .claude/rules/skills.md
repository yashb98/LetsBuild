# Rules: Skill Files (skills/**/*)

## Skill File Format

Every skill file uses `.skill.md` extension with YAML frontmatter:

```yaml
---
name: fullstack
display_name: "Full-Stack Web Application"
category: project  # project | codegen | research | content | template
role_categories:
  - full_stack_engineer
  - frontend_engineer
  - backend_engineer
seniority_range: [junior, mid, senior, staff]
tech_stacks:
  primary: ["React", "Next.js", "FastAPI", "PostgreSQL"]
  alternatives: ["Vue", "Django", "Express", "MySQL"]
complexity_range: [3, 8]
estimated_loc: [800, 3000]
sandbox_requirements:
  base_image: letsbuild/sandbox:latest
  extra_packages: ["postgresql-client"]
  timeout_minutes: 20
topology: hierarchical  # hierarchical | mesh | sequential | ring
---
```

## Skill Body Structure

After frontmatter, the skill body contains:

1. **## Overview** — What this skill generates and why
2. **## Project Templates** — 3-5 example projects with one-liners, scaled by seniority
3. **## Architecture Patterns** — Required patterns for this category (e.g., "all fullstack projects MUST have API + frontend + DB layers")
4. **## File Tree Template** — Expected directory structure
5. **## Quality Criteria** — What the QualityGate checks for this skill
6. **## Sandbox Validation Plan** — Exact bash commands that must pass
7. **## ADR Templates** — Pre-written ADR stubs relevant to this category
8. **## Common Failure Modes** — Known issues and how to avoid them (fed by ReasoningBank DISTILL)

## Naming Convention

- Project skills: `<category>.skill.md` (e.g., `fullstack.skill.md`)
- Code gen skills: `<language>-<framework>.skill.md` (e.g., `python-fastapi.skill.md`)
- Research skills: `<domain>-research.skill.md` (e.g., `fintech-research.skill.md`)
- Content skills: `<format>.skill.md` (e.g., `youtube.skill.md`)
- Template skills: `<type>-template.skill.md` (e.g., `readme-template.skill.md`)

## Progressive Loading

Skills are loaded on-demand by the SkillLoader middleware. A Python data science JD NEVER loads the React/Next.js codegen skill. The SkillLoader reads `role_categories` and `tech_stacks` from frontmatter to decide relevance.

## Adding a New Skill

1. Create `skills/<name>.skill.md` with correct frontmatter
2. Add at least 3 project templates covering junior/mid/senior
3. Define sandbox_validation_plan with ≥3 concrete commands
4. Add tests in `tests/skills/test_<name>_skill.py` verifying frontmatter parsing and template rendering
5. Run `/test-skill <name>` command to validate against a sample JD

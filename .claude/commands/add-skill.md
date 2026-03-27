# /add-skill — Scaffold a New Project Skill

Create a new skill file with correct frontmatter, section stubs, and a matching test file.

## Usage
```
/add-skill <skill_name> <category>
```

Example: `/add-skill robotics-ml project`

## Steps

1. Ask the user for:
   - Skill name (kebab-case)
   - Category: `project` | `codegen` | `research` | `content` | `template`
   - Target role categories (comma-separated)
   - Primary tech stack
   - Seniority range
   - Complexity range (1-10 min, 1-10 max)

2. Create `skills/<skill_name>.skill.md` with:
   - Full YAML frontmatter populated from user input
   - Section stubs for: Overview, Project Templates (3 entries), Architecture Patterns, File Tree Template, Quality Criteria, Sandbox Validation Plan, ADR Templates, Common Failure Modes

3. Create `tests/skills/test_<skill_name>_skill.py` with:
   - Test for frontmatter parsing
   - Test for required sections present
   - Test for sandbox_validation_plan has ≥3 commands

4. Print a summary of what was created and next steps

## Validation

Before creating, verify:
- Skill name doesn't already exist in `skills/`
- Category is valid
- At least one role_category is specified
- Tech stack has at least one item

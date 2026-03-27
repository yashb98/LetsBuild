---
description: "Research a specific technology, framework, or domain for skill file creation or architecture decisions. Produces a structured research brief."
context: fork
---

# Research Sprint Skill

Conduct focused research on a technology or domain to inform LetsBuild skill creation or architectural decisions.

## When to Use

- Creating a new project skill and need to understand the domain
- Evaluating a technology for the LetsBuild stack
- Investigating best practices for a specific framework
- Understanding what employers look for in a specific role category

## Research Template

### 1. Technology/Domain Overview
- What is it? One-paragraph summary
- Current version / maturity level
- Community size (GitHub stars, npm downloads, PyPI downloads)
- Major companies using it

### 2. Portfolio Project Landscape
- What are the most common portfolio projects in this space?
- What makes a project stand out to hiring managers?
- What are the "been done a million times" projects to avoid?
- What are 3 unique project ideas that showcase real skill?

### 3. Tech Stack Recommendations
- Primary stack (most requested by employers)
- Alternative stacks (for variety)
- Supporting tools (testing, CI/CD, monitoring)
- What NOT to use (deprecated, niche, or red-flag technologies)

### 4. Seniority Calibration
- Junior: What complexity level? What should they demonstrate?
- Mid: What additional patterns/concepts?
- Senior: What architectural depth? What scale?
- Staff: What system design? What cross-cutting concerns?

### 5. Common Failure Modes
- What breaks most often when AI generates code in this domain?
- What are the tricky edge cases?
- What requires domain expertise that LLMs often lack?

## Output

A structured markdown brief (1500-2500 words) saved to `docs/research/<topic>-brief.md` that can be referenced by skill authors and the Project Architect.

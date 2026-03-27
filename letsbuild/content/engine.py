"""Layer 7: Content Factory - orchestrates multi-format content generation."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from letsbuild.models.content_models import ContentFormat, ContentOutput

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec
    from letsbuild.models.forge_models import ForgeOutput
    from letsbuild.models.publisher_models import PublishResult

__all__ = ["ContentFactory"]

logger = structlog.get_logger(__name__)

# Platform mapping per format
_PLATFORM: dict[ContentFormat, str] = {
    ContentFormat.YOUTUBE_SCRIPT: "YouTube",
    ContentFormat.BLOG_POST: "Medium",
    ContentFormat.LINKEDIN_CAROUSEL: "LinkedIn",
    ContentFormat.TWITTER_THREAD: "Twitter",
    ContentFormat.PROJECT_WALKTHROUGH: "GitHub",
}


def _count_words(text: str) -> int:
    """Return the word count of *text*."""
    return len(text.split())


def _derive_seo_keywords(project_spec: ProjectSpec) -> list[str]:
    """Derive SEO keywords from project name, tech stack, and features."""
    keywords: list[str] = []
    # Project name words (split by space, dash, or underscore)
    import re

    name_parts = re.split(r"[\s\-_]+", project_spec.project_name.lower())
    keywords.extend(p for p in name_parts if len(p) > 2)

    # Tech stack (lowercase, de-duped)
    for tech in project_spec.tech_stack:
        kw = tech.lower().strip()
        if kw and kw not in keywords:
            keywords.append(kw)

    # Feature names
    for feat in project_spec.feature_specs[:5]:
        feat_parts = re.split(r"[\s\-_]+", feat.feature_name.lower())
        for part in feat_parts:
            if len(part) > 3 and part not in keywords:
                keywords.append(part)

    # Generic portfolio keywords
    extras = ["portfolio", "open source", "github", project_spec.seniority_target]
    for e in extras:
        if e and e.lower() not in keywords:
            keywords.append(e.lower())

    return keywords[:20]


class ContentFactory:
    """Generates marketing content for a published portfolio project.

    Supports five output formats: YouTube script, blog post, LinkedIn carousel,
    Twitter thread, and project walkthrough.  All generation is heuristic /
    template-based (no LLM calls) — the same pattern used by other layers for
    deterministic fallback output.
    """

    def __init__(self, formats: list[ContentFormat] | None = None) -> None:
        self._formats: list[ContentFormat] = formats if formats is not None else list(ContentFormat)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> list[ContentOutput]:
        """Generate all requested content formats in parallel.

        Args:
            project_spec: Layer 4 project specification.
            forge_output: Layer 5 forge output (used for quality/review info).
            publish_result: Layer 6 publish result containing the repo URL.

        Returns:
            List of :class:`~letsbuild.models.content_models.ContentOutput` instances,
            one per requested format.
        """
        log = logger.bind(
            project=project_spec.project_name,
            formats=[f.value for f in self._formats],
        )
        log.info("content_factory.generate.start")

        tasks = [
            self._dispatch(fmt, project_spec, forge_output, publish_result) for fmt in self._formats
        ]
        results: list[ContentOutput] = await asyncio.gather(*tasks)

        log.info("content_factory.generate.complete", count=len(results))
        return results

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        fmt: ContentFormat,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        generators = {
            ContentFormat.YOUTUBE_SCRIPT: self._generate_youtube_script,
            ContentFormat.BLOG_POST: self._generate_blog_post,
            ContentFormat.LINKEDIN_CAROUSEL: self._generate_linkedin_carousel,
            ContentFormat.TWITTER_THREAD: self._generate_twitter_thread,
            ContentFormat.PROJECT_WALKTHROUGH: self._generate_project_walkthrough,
        }
        gen = generators[fmt]
        output = await gen(project_spec, forge_output, publish_result)
        logger.debug("content_factory.format.done", format=fmt.value)
        return output

    # ------------------------------------------------------------------
    # Format generators
    # ------------------------------------------------------------------

    async def _generate_youtube_script(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        """Generate a 5-7 minute YouTube video script."""
        name = project_spec.project_name
        one_liner = project_spec.one_liner
        tech = ", ".join(project_spec.tech_stack[:6])
        repo_url = publish_result.repo_url
        features = project_spec.feature_specs[:4]
        feature_bullets = "\n".join(f"  - {f.feature_name}: {f.description}" for f in features)
        adrs = project_spec.adr_list[:2]
        adr_bullets = (
            "\n".join(f"  - {a.title}" for a in adrs) if adrs else "  - (see repo docs/decisions/)"
        )

        title = f"I Built {name} — Here's How ({project_spec.seniority_target.title()} Portfolio Project)"

        content = f"""\
# YouTube Script: {title}

---
## [HOOK — 0:00-0:20]

*[On screen: terminal / live demo clip]*

"What if you could {one_liner.lower().rstrip(".")}?  In this video, I'll show you \
exactly how I built {name} from scratch — the architecture decisions, the hardest \
bugs, and what I learned."

---
## [INTRO — 0:20-0:50]

Hey everyone — welcome back to the channel.  Today we're diving deep into **{name}**, \
a {project_spec.seniority_target}-level portfolio project I built to sharpen my skills \
in {tech}.

By the end of this video you'll see:
- The full architecture breakdown
- Live walkthrough of the key features
- The three biggest lessons I learned building this

The source code is 100 % open source — link in the description: {repo_url}

---
## [PROBLEM — 0:50-1:30]

*[Talking head / whiteboard]*

Here's the problem I set out to solve: {one_liner}

Most implementations of this either have X or Y limitation.  I wanted to build \
something production-ready — with tests, CI/CD, proper error handling, and real \
architecture decision records.

---
## [SOLUTION OVERVIEW — 1:30-2:30]

*[Architecture diagram]*

My solution is **{name}**.  Built with {tech}.

At a high level, the system has {len(project_spec.feature_specs)} core components:
{feature_bullets}

The key design principles I followed:
1. Clean separation of concerns
2. Testable from day one
3. Observable — logs and metrics everywhere

---
## [ARCHITECTURE DEEP-DIVE — 2:30-4:00]

*[Code walkthrough in editor]*

Let me show you the structure.  I'll start with the entry point and walk down \
through the layers.

*[Walk through file tree, highlight key modules]*

One of the most interesting decisions I made was captured in an Architecture \
Decision Record:

{adr_bullets}

I'll drop links to the full ADRs in the description.

---
## [FEATURE WALKTHROUGH — 4:00-5:30]

*[Live demo / screen recording]*

Now let me show you this in action.

{chr(10).join(f"**{f.feature_name}** — {f.description}" for f in features)}

*[Demo each feature]*

---
## [TESTING & QUALITY — 5:30-6:00]

The project has a quality score of **{forge_output.quality_score:.0f}/100** from \
the automated review.  Here's how the test suite looks:

*[Show test output in terminal]*

---
## [CALL TO ACTION — 6:00-6:30]

If you found this useful, hit the like button and subscribe — I'm building one \
of these every week.

**Links in the description:**
- GitHub repo: {repo_url}
- Full blog post with code explanations
- Architecture Decision Records in docs/decisions/

Drop any questions in the comments.  See you in the next one!

---
*[END SCREEN — 6:30]*
"""

        return ContentOutput(
            format=ContentFormat.YOUTUBE_SCRIPT,
            title=title,
            content=content,
            word_count=_count_words(content),
            target_platform=_PLATFORM[ContentFormat.YOUTUBE_SCRIPT],
            seo_keywords=_derive_seo_keywords(project_spec),
        )

    # ------------------------------------------------------------------

    async def _generate_blog_post(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        """Generate a 2000-3000 word technical blog post."""
        name = project_spec.project_name
        one_liner = project_spec.one_liner
        tech = ", ".join(project_spec.tech_stack)
        repo_url = publish_result.repo_url
        features = project_spec.feature_specs
        adrs = project_spec.adr_list

        feature_sections = ""
        for feat in features:
            criteria = "\n".join(f"- {c}" for c in feat.acceptance_criteria[:3])
            feature_sections += f"""
### {feat.feature_name}

{feat.description}

**Module:** `{feat.module_path}`
**Complexity:** {feat.estimated_complexity}/10

{f"Acceptance criteria:{chr(10)}{criteria}" if criteria else ""}
"""

        adr_sections = ""
        for adr in adrs[:3]:
            adr_sections += f"""
### ADR: {adr.title}

**Status:** {adr.status.value.title()}

**Context:** {adr.context}

**Decision:** {adr.decision}

**Consequences:** {adr.consequences}
"""

        review_note = (
            f"The independent code review returned a verdict of "
            f"**{forge_output.review_verdict.value.replace('_', ' ').title()}** "
            f"with a quality score of **{forge_output.quality_score:.0f}/100**."
        )

        passed_tests = sum(1 for v in forge_output.test_results.values() if v)
        total_tests = len(forge_output.test_results)
        test_summary = (
            f"{passed_tests}/{total_tests} tests passing"
            if total_tests > 0
            else "full test suite included in the repository"
        )

        title = f"Building {name}: A {project_spec.seniority_target.title()}-Level Portfolio Project with {project_spec.tech_stack[0] if project_spec.tech_stack else 'Modern Tech'}"

        content = f"""\
# {title}

> **TL;DR** — {one_liner}  Source code: [{repo_url}]({repo_url})

---

## Introduction

Portfolio projects live or die by one question: does this look like something a \
professional actually built, or does it look like a tutorial clone?

**{name}** is my answer to that question.  It is a {project_spec.seniority_target}-level \
project built with {tech}.  Every line of code was validated in a Docker sandbox before \
publishing, and every major architectural decision is captured in an Architecture \
Decision Record.

In this post I will walk you through:

1. The motivation and problem statement
2. The architecture and key design decisions
3. Each major feature with code highlights
4. How I approached testing and quality
5. The deployment pipeline
6. Lessons learned and what I would do differently

---

## Motivation

{one_liner}

Most existing solutions in this space are either too narrow or ship without \
production concerns like observability, error handling, and documented architecture \
decisions.  I wanted to build something I would be comfortable deploying in a real \
engineering organisation.

**Tech stack:** {tech}

**Estimated scope:** ~{project_spec.estimated_loc:,} lines of code across \
{len(project_spec.file_tree)} top-level modules.

---

## Architecture

The project is structured around clear separation of concerns.  Here is the \
high-level architecture:

```
{name}/
{"".join(f"├── {node.path}  # {node.description or ''}" + chr(10) for node in project_spec.file_tree[:8])}
```

**Key architectural principles:**

- **Single responsibility** — each module has one job
- **Dependency injection** — configuration and clients are injected, not hardcoded
- **Fail loudly** — errors surface early with structured context

{f"### Architecture Decision Records{chr(10)}{adr_sections}" if adr_sections else ""}

---

## Features

{name} ships with {len(features)} core features:

{feature_sections}

---

## Testing & Quality

{review_note}

The project includes {test_summary}.  I followed a test-first approach for the \
core business logic, and I used the sandbox validation plan to ensure the full \
stack runs end-to-end before any commit lands.

```bash
# Run the test suite
pytest tests/ -v --cov={name.lower().replace(" ", "_").replace("-", "_")} --cov-report=term-missing
```

---

## Deployment

The repository includes a full CI/CD pipeline with GitHub Actions.  On every push:

1. Lint and type-check with `ruff` and `mypy`
2. Run the test suite with coverage reporting
3. Build and validate the Docker image
4. (On `main`) Deploy to the target environment

See `.github/workflows/` in the repository for the full pipeline definition.

---

## Lessons Learned

Building this project reinforced a few principles I now consider non-negotiable \
for portfolio-quality work:

1. **Document decisions as you make them** — the ADRs took 30 minutes to write \
   and already saved me from second-guessing past choices.
2. **Run your code in a real environment from day one** — the sandbox caught three \
   environment-specific bugs that my local machine masked.
3. **Independent code review forces clarity** — having a second pass with fresh \
   eyes (even an automated one) caught ambiguous variable names and missing edge cases.

---

## What's Next

- Performance benchmarking under realistic load
- Additional integration test scenarios
- Expanded documentation and tutorials

---

## Source Code

The full source code is available at [{repo_url}]({repo_url}).

If you found this useful, please star the repo and share it with someone who is \
also building their portfolio.  Questions and PRs are very welcome!

---

*Built with {tech}.*
"""

        return ContentOutput(
            format=ContentFormat.BLOG_POST,
            title=title,
            content=content,
            word_count=_count_words(content),
            target_platform=_PLATFORM[ContentFormat.BLOG_POST],
            seo_keywords=_derive_seo_keywords(project_spec),
        )

    # ------------------------------------------------------------------

    async def _generate_linkedin_carousel(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        """Generate an 8-10 slide LinkedIn carousel."""
        name = project_spec.project_name
        one_liner = project_spec.one_liner
        tech = ", ".join(project_spec.tech_stack[:5])
        repo_url = publish_result.repo_url
        features = project_spec.feature_specs[:4]

        slides: list[str] = []

        # Slide 1 — Title
        slides.append(f"""\
--- SLIDE 1: TITLE ---
🚀 I built {name}

{one_liner}

({project_spec.seniority_target.title()} Portfolio Project)
→ Swipe to see how
""")

        # Slide 2 — Problem
        slides.append("""\
--- SLIDE 2: THE PROBLEM ---
Most devs build tutorial clones.

❌ No architecture decisions
❌ No real tests
❌ Never runs in production

I wanted to fix that.
""")

        # Slide 3 — Solution
        slides.append(f"""\
--- SLIDE 3: THE SOLUTION ---
{name}

✅ {one_liner}

Built with: {tech}
""")

        # Slide 4 — Architecture
        slides.append(f"""\
--- SLIDE 4: ARCHITECTURE ---
{len(project_spec.file_tree)} modules. Clean structure.

{chr(10).join(f"• {node.path}" for node in project_spec.file_tree[:6])}

Every decision is documented in an ADR.
""")

        # Slides 5-8 — Features
        for i, feat in enumerate(features, start=5):
            slides.append(f"""\
--- SLIDE {i}: FEATURE {i - 4} ---
{feat.feature_name}

{feat.description}

Complexity: {"★" * feat.estimated_complexity}{"☆" * (10 - feat.estimated_complexity)}
""")

        # Slide 9 — Tech stack
        tech_bullets = "\n".join(f"• {t}" for t in project_spec.tech_stack[:8])
        slides.append(f"""\
--- SLIDE {len(slides) + 1}: TECH STACK ---
What I used to build it:

{tech_bullets}
""")

        # Slide 10 — CTA
        slides.append(f"""\
--- SLIDE {len(slides) + 1}: CALL TO ACTION ---
The full source code is on GitHub.

⭐ Star the repo: {repo_url}

Quality score: {forge_output.quality_score:.0f}/100
Review verdict: {forge_output.review_verdict.value.replace("_", " ").title()}

What would you add next? Drop it in the comments 👇
""")

        title = f"I Built {name} — A {project_spec.seniority_target.title()} Portfolio Project [{len(slides)} Slides]"
        content_body = "\n".join(slides)

        return ContentOutput(
            format=ContentFormat.LINKEDIN_CAROUSEL,
            title=title,
            content=content_body,
            word_count=_count_words(content_body),
            target_platform=_PLATFORM[ContentFormat.LINKEDIN_CAROUSEL],
            seo_keywords=_derive_seo_keywords(project_spec),
        )

    # ------------------------------------------------------------------

    async def _generate_twitter_thread(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        """Generate a 10-15 tweet Twitter/X thread."""
        name = project_spec.project_name
        one_liner = project_spec.one_liner
        tech = ", ".join(project_spec.tech_stack[:4])
        repo_url = publish_result.repo_url
        features = project_spec.feature_specs[:5]

        tweets: list[str] = []

        # Tweet 1 — Hook
        tweets.append(
            f"1/ I spent the last few weeks building {name}.\n\n"
            f"{one_liner}\n\n"
            f"Here's what I built, how I built it, and what I learned 🧵"
        )

        # Tweet 2 — Problem
        tweets.append(
            "2/ The problem:\n\n"
            "Most portfolio projects are:\n"
            "❌ Tutorial clones\n"
            "❌ Missing tests\n"
            "❌ No architecture documentation\n\n"
            "I wanted to build something that looks like real engineering."
        )

        # Tweet 3 — Solution
        tweets.append(
            f"3/ The solution: {name}\n\n"
            f"Tech stack: {tech}\n\n"
            f"~{project_spec.estimated_loc:,} lines of code\n"
            f"Seniority target: {project_spec.seniority_target}"
        )

        # Tweet 4 — Architecture
        top_modules = ", ".join(node.path for node in project_spec.file_tree[:4])
        tweets.append(
            f"4/ The architecture:\n\n"
            f"Core modules: {top_modules}\n\n"
            f"Every major decision is documented in an Architecture Decision Record (ADR).\n\n"
            f"This is how senior engineers work."
        )

        # Tweet 5-9 — Features
        for i, feat in enumerate(features, start=5):
            tweets.append(
                f"{i}/ Feature: {feat.feature_name}\n\n"
                f"{feat.description}\n\n"
                f"Complexity: {feat.estimated_complexity}/10"
            )

        # Tweet for testing
        passed = sum(1 for v in forge_output.test_results.values() if v)
        total = len(forge_output.test_results)
        tweet_num = len(tweets) + 1
        if total > 0:
            tweets.append(
                f"{tweet_num}/ Testing:\n\n"
                f"{passed}/{total} tests passing\n\n"
                f"Quality score: {forge_output.quality_score:.0f}/100\n"
                f"Review verdict: {forge_output.review_verdict.value.replace('_', ' ').title()}"
            )
        else:
            tweets.append(
                f"{tweet_num}/ Quality:\n\n"
                f"Score: {forge_output.quality_score:.0f}/100\n"
                f"Review: {forge_output.review_verdict.value.replace('_', ' ').title()}\n\n"
                f"Full test suite in the repo."
            )

        # Code snippet tweet
        tweet_num = len(tweets) + 1
        if project_spec.feature_specs:
            feat0 = project_spec.feature_specs[0]
            tweets.append(
                f"{tweet_num}/ Here's the heart of the project — `{feat0.module_path}`:\n\n"
                f"```python\n# {feat0.feature_name}\n# {feat0.description}\n```\n\n"
                f"Clean, typed, tested."
            )

        # CTA tweet
        tweet_num = len(tweets) + 1
        tweets.append(
            f"{tweet_num}/ The full source code is open source.\n\n"
            f"⭐ Star it: {repo_url}\n\n"
            f"If this was useful, RT tweet 1 so other devs can see it.\n\n"
            f"What should I build next? Reply below 👇"
        )

        title = f"{name} — Twitter/X Thread ({len(tweets)} tweets)"
        content_body = "\n\n---\n\n".join(tweets)

        return ContentOutput(
            format=ContentFormat.TWITTER_THREAD,
            title=title,
            content=content_body,
            word_count=_count_words(content_body),
            target_platform=_PLATFORM[ContentFormat.TWITTER_THREAD],
            seo_keywords=_derive_seo_keywords(project_spec),
        )

    # ------------------------------------------------------------------

    async def _generate_project_walkthrough(
        self,
        project_spec: ProjectSpec,
        forge_output: ForgeOutput,
        publish_result: PublishResult,
    ) -> ContentOutput:
        """Generate a step-by-step project walkthrough guide."""
        name = project_spec.project_name
        one_liner = project_spec.one_liner
        tech = ", ".join(project_spec.tech_stack)
        repo_url = publish_result.repo_url
        features = project_spec.feature_specs

        # Derive primary language from tech stack heuristic
        primary_lang = "python"
        for t in project_spec.tech_stack:
            t_lower = t.lower()
            if "typescript" in t_lower or "node" in t_lower or "react" in t_lower:
                primary_lang = "typescript"
                break

        install_cmd = 'pip install -e ".[dev]"' if primary_lang == "python" else "npm install"
        run_cmd = "python -m app" if primary_lang == "python" else "npm run dev"
        test_cmd = "pytest tests/ -v" if primary_lang == "python" else "npm test"

        validation_steps = "\n".join(
            f"{i + 1}. `{cmd.command}` — {cmd.description}"
            for i, cmd in enumerate(project_spec.sandbox_validation_plan.commands[:5])
        )

        feature_walkthrough = ""
        for step_num, feat in enumerate(features, start=1):
            criteria_text = ""
            if feat.acceptance_criteria:
                criteria_text = "\n**Acceptance criteria:**\n" + "\n".join(
                    f"- {c}" for c in feat.acceptance_criteria[:3]
                )
            feature_walkthrough += f"""
### Step {step_num + 2}: {feat.feature_name}

**Module:** `{feat.module_path}`

{feat.description}
{criteria_text}
"""

        adr_table = ""
        if project_spec.adr_list:
            rows = "\n".join(
                f"| {a.title} | {a.status.value.title()} |" for a in project_spec.adr_list
            )
            adr_table = f"""
## Architecture Decision Records

| Decision | Status |
|----------|--------|
{rows}

Full ADRs are in `docs/decisions/`.
"""

        title = f"{name}: Complete Project Walkthrough"

        content = f"""\
# {title}

> {one_liner}

**Repository:** [{repo_url}]({repo_url})
**Tech stack:** {tech}
**Seniority target:** {project_spec.seniority_target.title()}
**Estimated LOC:** ~{project_spec.estimated_loc:,}

---

## Overview

{one_liner}

This walkthrough covers setup, architecture, each feature, testing, and deployment.

---

## Step 1: Setup & Installation

**Prerequisites:**
- Git
- {project_spec.tech_stack[0] if project_spec.tech_stack else "Required runtime"} (see README for version)
- Docker (optional, for sandbox validation)

```bash
# Clone the repository
git clone {repo_url}
cd {publish_result.repo_config.repo_name}

# Install dependencies
{install_cmd}

# Copy environment variables
cp .env.example .env
# Edit .env and fill in your values
```

---

## Step 2: Architecture Overview

The project is organised into {len(project_spec.file_tree)} top-level modules:

```
{name}/
{"".join(f"├── {node.path}  # {node.description or ''}" + chr(10) for node in project_spec.file_tree)}
```

**Design principles:**
- Single responsibility — each module has one well-defined job
- Dependency injection — all external clients are injected, not hardcoded
- Typed throughout — strict type checking enabled

{adr_table}

---
{feature_walkthrough}

---

## Testing

Run the full test suite:

```bash
{test_cmd}
```

**Sandbox validation commands** (run in Docker):

{validation_steps}

**Quality metrics from automated review:**
- Quality score: {forge_output.quality_score:.0f}/100
- Review verdict: {forge_output.review_verdict.value.replace("_", " ").title()}
- Review comments:
{chr(10).join(f"  - {c}" for c in forge_output.review_comments[:5]) if forge_output.review_comments else "  - (see repository for full review output)"}

---

## Running the Project

```bash
{run_cmd}
```

---

## Deployment

The repository includes a GitHub Actions CI/CD pipeline located in `.github/workflows/`.

The pipeline:
1. Lints and type-checks the code
2. Runs the full test suite with coverage
3. Builds and pushes the Docker image
4. Deploys on merge to `main`

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit using Conventional Commits: `git commit -m "feat: add ..."`
4. Open a pull request

---

## Source Code

**GitHub:** [{repo_url}]({repo_url})

If you found this helpful, please star the repository ⭐
"""

        return ContentOutput(
            format=ContentFormat.PROJECT_WALKTHROUGH,
            title=title,
            content=content,
            word_count=_count_words(content),
            target_platform=_PLATFORM[ContentFormat.PROJECT_WALKTHROUGH],
            seo_keywords=_derive_seo_keywords(project_spec),
        )

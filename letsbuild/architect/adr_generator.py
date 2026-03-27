"""Architecture Decision Record generator for Layer 4: Project Architect."""

from __future__ import annotations

import structlog

from letsbuild.models.architect_models import ADR, ADRStatus

logger = structlog.get_logger()

# Mapping of tech stack keywords to ADR content templates.
# Each entry: (title, context, decision, consequences)
_TECH_ADR_MAP: dict[str, tuple[str, str, str, str]] = {
    "fastapi": (
        "Use FastAPI for API layer",
        "The project requires an HTTP API layer that supports async request handling, "
        "automatic OpenAPI documentation, and high throughput. Several Python web frameworks "
        "were considered including Flask, Django REST Framework, and FastAPI. The team needs "
        "strong typing integration and Pydantic-based validation out of the box.",
        "We chose FastAPI as the primary API framework because it offers native async support, "
        "automatic request/response validation via Pydantic, and auto-generated OpenAPI/Swagger "
        "documentation. Its performance benchmarks consistently place it among the fastest Python "
        "web frameworks, and its dependency injection system simplifies testing.",
        "FastAPI provides excellent developer experience and performance but has a smaller "
        "ecosystem of third-party extensions compared to Django. The team must be comfortable "
        "with async/await patterns. Deployment requires an ASGI server such as Uvicorn. "
        "Future migration to another framework would require rewriting route definitions.",
    ),
    "flask": (
        "Use Flask for API layer",
        "The project needs a lightweight HTTP API layer. Flask is a mature micro-framework "
        "with a large ecosystem of extensions. The team evaluated Flask, FastAPI, and Django "
        "for the API layer, weighing simplicity against feature richness.",
        "We chose Flask for its simplicity, maturity, and extensive plugin ecosystem. Flask's "
        "minimal core allows the team to pick exactly the components needed without imposing "
        "opinionated structure. The large community ensures strong documentation and support.",
        "Flask is synchronous by default, which may limit throughput under heavy concurrent "
        "load. Async support requires additional libraries. The lack of built-in validation "
        "means the team must integrate libraries like Marshmallow or Pydantic separately.",
    ),
    "react": (
        "Use React for frontend UI",
        "The frontend needs a component-based architecture that supports complex interactive "
        "UIs with efficient DOM updates. The team evaluated React, Vue, Svelte, and Angular. "
        "Developer familiarity and ecosystem breadth were key factors in the decision.",
        "We chose React for its mature ecosystem, extensive component libraries, and wide "
        "industry adoption. React's virtual DOM and reconciliation algorithm provide efficient "
        "rendering. The hooks API enables clean state management without class components, and "
        "the large talent pool simplifies future hiring.",
        "React introduces a JSX build step and requires bundler configuration. The library is "
        "unopinionated about routing and state management, requiring additional libraries like "
        "React Router and Zustand/Redux. Bundle size must be monitored to avoid performance "
        "degradation on low-bandwidth connections.",
    ),
    "next.js": (
        "Use Next.js for frontend framework",
        "The project requires server-side rendering, static generation, and API routes within "
        "a unified React framework. The team needs file-system-based routing, image optimization, "
        "and built-in performance features. Next.js, Remix, and Gatsby were evaluated.",
        "We chose Next.js for its comprehensive feature set including SSR, SSG, ISR, and API "
        "routes in a single framework. The App Router architecture provides React Server "
        "Components support, reducing client-side JavaScript. Vercel's deployment platform "
        "offers seamless integration, though self-hosting is also well supported.",
        "Next.js ties the project to the React ecosystem and introduces Vercel-specific "
        "conventions. The framework's rapid release cadence means the team must stay current "
        "with breaking changes. Server Components add conceptual complexity and require careful "
        "consideration of the client/server boundary.",
    ),
    "postgresql": (
        "Use PostgreSQL for data persistence",
        "The application requires a relational database with strong ACID guarantees, support "
        "for complex queries, and extensibility. PostgreSQL, MySQL, and SQLite were considered. "
        "The data model includes relationships, full-text search needs, and JSON storage.",
        "We chose PostgreSQL for its robust feature set including JSONB columns, full-text "
        "search, CTEs, window functions, and excellent concurrent write performance. Its "
        "extension ecosystem (PostGIS, pgvector, TimescaleDB) allows future expansion without "
        "changing the database engine.",
        "PostgreSQL requires separate server management and has higher operational overhead "
        "compared to SQLite. Connection pooling (via PgBouncer or similar) is needed at scale. "
        "Some cloud providers charge premium pricing for managed PostgreSQL instances compared "
        "to MySQL equivalents.",
    ),
    "mysql": (
        "Use MySQL for data persistence",
        "The application needs a production-grade relational database with strong read "
        "performance, wide hosting support, and proven reliability at scale. MySQL, PostgreSQL, "
        "and MariaDB were evaluated for the persistence layer.",
        "We chose MySQL for its exceptional read performance, widespread hosting availability, "
        "and mature replication support. MySQL's InnoDB engine provides ACID compliance, and "
        "the database is supported by virtually every hosting provider and cloud platform.",
        "MySQL has fewer advanced SQL features than PostgreSQL (limited CTEs, window functions "
        "in older versions). JSON support is less mature. The team must carefully choose the "
        "storage engine and character set configuration to avoid common pitfalls.",
    ),
    "docker": (
        "Containerize application with Docker",
        "The project needs consistent development, testing, and production environments. "
        "Works-on-my-machine issues must be eliminated, and deployment should be reproducible. "
        "Docker, Vagrant, and Nix were evaluated as environment standardization tools.",
        "We chose Docker for containerization because it provides lightweight, reproducible "
        "environments with broad industry adoption. Multi-stage builds minimize image size, "
        "and Docker Compose simplifies local multi-service development. CI/CD pipelines "
        "integrate seamlessly with container registries.",
        "Docker adds a build step to the development workflow and requires developers to "
        "understand container concepts. Image layer caching must be optimized to avoid slow "
        "builds. Security scanning of base images is necessary to avoid known vulnerabilities. "
        "Persistent storage requires volume management.",
    ),
    "pytorch": (
        "Use PyTorch for machine learning",
        "The project involves training and deploying machine learning models. The team needs "
        "a framework that supports dynamic computation graphs, has strong GPU acceleration, "
        "and integrates well with the Python data science ecosystem. PyTorch, TensorFlow, "
        "and JAX were evaluated.",
        "We chose PyTorch for its intuitive dynamic computation graph, Pythonic API, and "
        "dominant position in ML research. PyTorch's eager execution mode simplifies debugging, "
        "and TorchScript provides a path to production optimization. The ecosystem includes "
        "Hugging Face Transformers, torchvision, and torchaudio.",
        "PyTorch models require explicit export (TorchScript/ONNX) for production serving, "
        "unlike TensorFlow's SavedModel format. Mobile deployment is less mature than "
        "TensorFlow Lite. Memory management requires attention to avoid GPU OOM errors in "
        "training loops.",
    ),
    "tensorflow": (
        "Use TensorFlow for machine learning",
        "The project requires a production-grade ML framework with strong deployment tooling, "
        "mobile support, and a mature serving infrastructure. TensorFlow, PyTorch, and JAX "
        "were considered based on model complexity and deployment requirements.",
        "We chose TensorFlow for its comprehensive deployment ecosystem including TF Serving, "
        "TF Lite, and TF.js. The Keras API provides a high-level interface for rapid "
        "prototyping, while the lower-level API supports custom training loops. TensorBoard "
        "offers built-in experiment tracking.",
        "TensorFlow's graph-based execution can complicate debugging compared to eager-mode "
        "frameworks. The API has undergone significant changes between versions, and some "
        "community resources reference deprecated patterns. The framework's size impacts "
        "installation time and container image size.",
    ),
    "kubernetes": (
        "Use Kubernetes for orchestration",
        "The application requires automated scaling, self-healing, and service discovery "
        "across multiple containers. The team evaluated Kubernetes, Docker Swarm, and Nomad "
        "for container orchestration. High availability and zero-downtime deployments are "
        "critical requirements.",
        "We chose Kubernetes for its industry-standard orchestration capabilities including "
        "declarative configuration, automatic scaling, rolling updates, and a rich ecosystem "
        "of operators and tools. Managed Kubernetes services (EKS, GKE, AKS) reduce "
        "operational burden while maintaining portability.",
        "Kubernetes introduces significant operational complexity and a steep learning curve. "
        "YAML configuration can become unwieldy without templating tools like Helm or Kustomize. "
        "Resource overhead for the control plane is non-trivial for small deployments. The team "
        "must invest in monitoring and observability tooling.",
    ),
}


class ADRGenerator:
    """Generates Architecture Decision Records for project specifications.

    This generator produces ADRs deterministically from tech stack choices
    and skill file templates. It does not make LLM calls — all content is
    derived from predefined templates and expansion logic.
    """

    def __init__(self) -> None:
        self._logger = logger.bind(component="adr_generator")
        self._counter: int = 0

    def _next_id(self) -> str:
        """Return the next incrementing ADR ID (e.g. ADR-001, ADR-002)."""
        self._counter += 1
        return f"ADR-{self._counter:03d}"

    def generate(
        self,
        project_name: str,
        tech_choices: list[str],
        skill_adr_templates: list[str] | None = None,
    ) -> list[ADR]:
        """Generate ADRs for a project based on tech choices and optional templates.

        Always returns at least 2 ADRs. If tech_choices and templates together
        produce fewer than 2, a default project-structure ADR is appended.

        Args:
            project_name: Name of the project being designed.
            tech_choices: List of technologies chosen for the project.
            skill_adr_templates: Optional ADR template strings from skill files.

        Returns:
            List of ADR models with substantive content.
        """
        self._logger.info(
            "generating_adrs",
            project_name=project_name,
            tech_count=len(tech_choices),
            template_count=len(skill_adr_templates) if skill_adr_templates else 0,
        )

        adrs: list[ADR] = []

        # Generate ADRs from tech stack choices.
        adrs.extend(self.generate_from_tech_stack(tech_choices))

        # Generate ADRs from skill templates if provided.
        if skill_adr_templates:
            adrs.extend(self.generate_from_templates(skill_adr_templates))

        # Ensure at least 2 ADRs by adding defaults.
        if len(adrs) < 2:
            adrs.extend(self._generate_defaults(project_name, count=2 - len(adrs)))

        self._logger.info("adrs_generated", count=len(adrs), project_name=project_name)
        return adrs

    def generate_from_tech_stack(self, tech_stack: list[str]) -> list[ADR]:
        """Generate ADRs deterministically from a tech stack list.

        Matches tech stack items (case-insensitive) against known technology
        templates and produces an ADR for each match.

        Args:
            tech_stack: List of technology names (e.g. ["FastAPI", "PostgreSQL"]).

        Returns:
            List of ADR models for recognized technologies.
        """
        adrs: list[ADR] = []
        seen_keys: set[str] = set()

        for tech in tech_stack:
            key = tech.lower().strip()
            if key in _TECH_ADR_MAP and key not in seen_keys:
                seen_keys.add(key)
                title, context, decision, consequences = _TECH_ADR_MAP[key]
                adrs.append(
                    ADR(
                        adr_id=self._next_id(),
                        title=title,
                        status=ADRStatus.ACCEPTED,
                        context=context,
                        decision=decision,
                        consequences=consequences,
                    )
                )
                self._logger.debug("adr_from_tech", tech=tech, adr_id=adrs[-1].adr_id)

        return adrs

    def generate_from_templates(self, templates: list[str]) -> list[ADR]:
        """Expand brief ADR template strings into full ADR models.

        Each template is a short description (e.g. "Use event sourcing for audit trail")
        that gets expanded into a complete ADR with context, decision, and consequences.

        Args:
            templates: List of brief ADR description strings.

        Returns:
            List of expanded ADR models.
        """
        adrs: list[ADR] = []

        for template in templates:
            template = template.strip()
            if not template:
                continue

            adrs.append(
                ADR(
                    adr_id=self._next_id(),
                    title=template,
                    status=ADRStatus.ACCEPTED,
                    context=(
                        f"The project requires a decision on: {template}. "
                        "This architectural choice affects the overall system design, "
                        "maintainability, and developer experience. Multiple alternatives "
                        "were considered before arriving at this decision."
                    ),
                    decision=(
                        f"We decided to {template.lower()}. "
                        "This approach was selected after evaluating alternatives based on "
                        "project requirements, team expertise, and long-term maintainability. "
                        "The decision aligns with industry best practices for this domain."
                    ),
                    consequences=(
                        f"Adopting this decision means the team commits to the patterns "
                        f"implied by: {template}. This provides clear architectural direction "
                        "but limits flexibility to pivot to alternative approaches later. "
                        "The team should revisit this decision if requirements change significantly."
                    ),
                )
            )
            self._logger.debug("adr_from_template", template=template, adr_id=adrs[-1].adr_id)

        return adrs

    def _generate_defaults(self, project_name: str, count: int) -> list[ADR]:
        """Generate default ADRs to meet the minimum threshold.

        Args:
            project_name: Name of the project.
            count: Number of default ADRs to generate.

        Returns:
            List of default ADR models.
        """
        defaults: list[ADR] = []

        default_templates = [
            (
                f"Adopt modular architecture for {project_name}",
                "The project needs a clear architectural structure that supports independent "
                "development, testing, and deployment of components. A monolithic approach was "
                "considered but rejected due to coupling concerns and difficulty scaling the "
                "development process across features.",
                "We adopt a modular architecture with clearly defined module boundaries and "
                "explicit dependency directions. Each module exposes a public API and hides "
                "implementation details. Inter-module communication uses well-defined interfaces "
                "rather than direct imports of internal classes.",
                "Modular architecture requires upfront investment in defining boundaries and "
                "interfaces. It may introduce indirection that feels unnecessary for small "
                "projects. However, it pays dividends in testability, maintainability, and "
                "the ability to evolve individual modules independently.",
            ),
            (
                f"Use comprehensive testing strategy for {project_name}",
                "The project must maintain high code quality and prevent regressions as features "
                "are added. The team needs a clear testing strategy that covers unit, integration, "
                "and end-to-end scenarios without creating an unmaintainable test suite.",
                "We implement a testing pyramid with unit tests at the base, integration tests "
                "in the middle, and a small number of end-to-end tests at the top. All public "
                "interfaces have unit tests. Critical paths have integration tests. The CI "
                "pipeline runs the full suite on every pull request.",
                "A comprehensive testing strategy increases development time per feature but "
                "reduces debugging time and prevents regressions. The team must maintain test "
                "quality alongside production code quality. Flaky tests must be fixed immediately "
                "to preserve trust in the test suite.",
            ),
        ]

        for i in range(min(count, len(default_templates))):
            title, context, decision, consequences = default_templates[i]
            defaults.append(
                ADR(
                    adr_id=self._next_id(),
                    title=title,
                    status=ADRStatus.ACCEPTED,
                    context=context,
                    decision=decision,
                    consequences=consequences,
                )
            )

        return defaults

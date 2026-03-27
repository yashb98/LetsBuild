"""PipelineController — orchestrates layers 1-5 sequentially with middleware wrapping.

Executes L1 Intake -> L2 Intelligence -> L3 Matcher -> L4 Architect -> L5 Code Forge,
running middleware before/after each layer and tracking metrics. Handles errors with
structured error accumulation and aborts if >= 3 layers fail.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from letsbuild.architect.engine import ProjectArchitect
from letsbuild.forge.agents.integrator import IntegratorAgent
from letsbuild.forge.agents.planner import PlannerAgent
from letsbuild.forge.agents.reviewer import ReviewerAgent
from letsbuild.forge.agents.tester import TesterAgent
from letsbuild.forge.executor import ForgeExecutor
from letsbuild.forge.topology import TopologySelector
from letsbuild.harness.middleware import MiddlewareChain  # noqa: TC001
from letsbuild.intake.engine import IntakeEngine
from letsbuild.intelligence.coordinator import IntelligenceCoordinator
from letsbuild.matcher.engine import MatchEngine
from letsbuild.models.forge_models import CodeModule, ForgeOutput
from letsbuild.models.shared import ErrorCategory, StructuredError
from letsbuild.pipeline.state import PipelineState

if TYPE_CHECKING:
    from letsbuild.models.config_models import AppConfig

logger = structlog.get_logger()

_LAYER_NAMES: dict[int, str] = {
    1: "intake",
    2: "intelligence",
    3: "matcher",
    4: "architect",
    5: "forge",
}


class PipelineController:
    """Orchestrates the full LetsBuild pipeline from JD to ForgeOutput.

    Currently implements layers 1-5. Layers 6-7 (Publisher, Content)
    are not yet wired and will be added in future iterations.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config
        self._log = logger.bind(component="pipeline_controller")

        # Layer engines — created eagerly so callers can swap them for mocks
        self.intake_engine = IntakeEngine()
        self.intelligence_coordinator = IntelligenceCoordinator()
        self.match_engine = MatchEngine()
        self.project_architect = ProjectArchitect()

        # Middleware chain — empty by default; callers can inject via set_middleware_chain
        self._middleware_chain: MiddlewareChain | None = None

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    def set_middleware_chain(self, chain: MiddlewareChain) -> None:
        """Replace the middleware chain used to wrap layer execution."""
        self._middleware_chain = chain

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        jd_text: str | None = None,
        jd_url: str | None = None,
    ) -> PipelineState:
        """Execute layers 1-5 sequentially and return the accumulated state.

        Args:
            jd_text: Raw job description text.
            jd_url: URL to fetch the job description from.

        Returns:
            PipelineState with results from each completed layer.

        Raises:
            ValueError: If neither *jd_text* nor *jd_url* is provided.
        """
        if jd_text is None and jd_url is None:
            msg = "Either jd_text or jd_url must be provided."
            raise ValueError(msg)

        state = PipelineState(jd_text=jd_text, jd_url=jd_url)
        self._log.info("pipeline_start", thread_id=state.thread_id)
        pipeline_start = time.monotonic()

        for layer_num in range(1, 6):
            if state.is_failed():
                self._log.warning(
                    "pipeline_abort",
                    thread_id=state.thread_id,
                    reason="too_many_errors",
                    error_count=len(state.errors),
                )
                break

            state = await self.run_layer(layer_num, state)

        total_elapsed = time.monotonic() - pipeline_start
        state.metrics.total_duration_seconds = round(total_elapsed, 3)
        state.completed_at = datetime.now(UTC)

        self._log.info(
            "pipeline_complete",
            thread_id=state.thread_id,
            total_seconds=state.metrics.total_duration_seconds,
            errors=len(state.errors),
        )
        return state

    async def run_layer(self, layer_num: int, state: PipelineState) -> PipelineState:
        """Execute a single layer, wrapped by middleware if configured.

        Args:
            layer_num: Layer number (1-5 currently supported).
            state: The current pipeline state.

        Returns:
            Updated pipeline state with the layer's output (or an appended error).
        """
        state.current_layer = layer_num
        layer_name = _LAYER_NAMES.get(layer_num, f"layer_{layer_num}")
        self._log.info("layer_start", layer=layer_num, name=layer_name)

        async def _execute(s: PipelineState) -> PipelineState:
            return await self._dispatch_layer(layer_num, s)

        start = time.monotonic()
        try:
            if self._middleware_chain is not None:
                state = await self._middleware_chain.execute(state, _execute)
            else:
                state = await _execute(state)
        except Exception as exc:
            elapsed = time.monotonic() - start
            self._log.error(
                "layer_failed",
                layer=layer_num,
                name=layer_name,
                error=str(exc),
                elapsed_seconds=round(elapsed, 3),
            )
            state.add_error(
                StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message=f"Layer {layer_num} ({layer_name}) failed: {exc}",
                    attempted_query=layer_name,
                )
            )
        else:
            elapsed = time.monotonic() - start
            state.metrics.layer_durations[layer_name] = round(elapsed, 3)
            self._log.info(
                "layer_complete",
                layer=layer_num,
                name=layer_name,
                elapsed_seconds=round(elapsed, 3),
            )

        return state

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch_layer(self, layer_num: int, state: PipelineState) -> PipelineState:
        """Route to the correct layer engine based on *layer_num*."""
        if layer_num == 1:
            return await self._run_intake(state)
        if layer_num == 2:
            return await self._run_intelligence(state)
        if layer_num == 3:
            return await self._run_matcher(state)
        if layer_num == 4:
            return await self._run_architect(state)
        if layer_num == 5:
            return await self._run_forge(state)

        msg = f"Layer {layer_num} is not implemented yet."
        raise NotImplementedError(msg)

    # ------------------------------------------------------------------
    # Layer runners
    # ------------------------------------------------------------------

    async def _run_intake(self, state: PipelineState) -> PipelineState:
        """L1 — parse JD text (or fetch from URL) into JDAnalysis."""
        if state.jd_url and not state.jd_text:
            analysis = await self.intake_engine.parse_from_url(state.jd_url)
        elif state.jd_text:
            analysis = await self.intake_engine.parse_jd(state.jd_text, source_url=state.jd_url)
        else:
            msg = "No JD text or URL available for intake."
            raise ValueError(msg)

        state.jd_analysis = analysis
        return state

    async def _run_intelligence(self, state: PipelineState) -> PipelineState:
        """L2 — research company from JD analysis."""
        if state.jd_analysis is None:
            msg = "Cannot run L2 intelligence without L1 jd_analysis."
            raise ValueError(msg)

        company_name = state.jd_analysis.company_name or "Unknown Company"
        company_url = state.jd_analysis.company_url
        jd_text = state.jd_text

        result = await self.intelligence_coordinator.research_company(
            company_name=company_name,
            company_url=company_url,
            jd_text=jd_text,
        )
        state.company_profile = result.company_profile
        return state

    async def _run_matcher(self, state: PipelineState) -> PipelineState:
        """L3 — score and categorise skill gaps."""
        if state.jd_analysis is None:
            msg = "Cannot run L3 matcher without L1 jd_analysis."
            raise ValueError(msg)

        gap_analysis = await self.match_engine.analyse(
            jd_analysis=state.jd_analysis,
            company_profile=state.company_profile,
        )
        state.gap_analysis = gap_analysis
        return state

    async def _run_architect(self, state: PipelineState) -> PipelineState:
        """L4 — design project specification."""
        if state.jd_analysis is None:
            msg = "Cannot run L4 architect without L1 jd_analysis."
            raise ValueError(msg)

        skill_config = state.skill_configs[0] if state.skill_configs else None

        spec = await self.project_architect.design(
            jd_analysis=state.jd_analysis,
            company_profile=state.company_profile,
            gap_analysis=state.gap_analysis,
            skill_config=skill_config,
        )
        state.project_spec = spec
        return state

    async def _run_forge(self, state: PipelineState) -> PipelineState:
        """L5 — generate code via the Code Forge multi-agent pipeline.

        Steps:
        1. Plan tasks from ``state.project_spec`` via PlannerAgent.
        2. Select topology via TopologySelector.
        3. Execute tasks via ForgeExecutor (heuristic fallback if no LLM).
        4. Test code via TesterAgent.
        5. Review code via ReviewerAgent (independent — no coder context).
        6. Integrate code via IntegratorAgent.
        7. Assemble and return ForgeOutput.
        """
        if state.project_spec is None:
            msg = "Cannot run L5 forge without L4 project_spec."
            raise ValueError(msg)

        project_spec = state.project_spec

        # 1. Plan
        planner = PlannerAgent(llm_client=None)
        task_graph = await planner.plan(project_spec)

        # 2. Topology selection
        topology_selector = TopologySelector()
        topology = topology_selector.select(project_spec)
        task_graph.topology = topology

        # 3. Execute (code generation)
        executor = ForgeExecutor(llm_client=None)
        agent_outputs = await executor.execute_tasks(
            task_graph,
            project_context=f"Project: {project_spec.project_name} — {project_spec.one_liner}",
        )

        # Collect code modules from all agent outputs
        code_modules: list[CodeModule] = []
        for output in agent_outputs:
            code_modules.extend(output.output_modules)

        # 4. Test
        tester = TesterAgent(llm_client=None)
        test_output = await tester.test(code_modules, test_plan="Run all sandbox validation tests")

        # 5. Review (independent — no coder context)
        reviewer = ReviewerAgent(llm_client=None)
        review_result = await reviewer.review(
            code_modules=code_modules,
            project_spec_summary=f"{project_spec.project_name}: {project_spec.one_liner}",
        )

        # 6. Integrate
        integrator = IntegratorAgent(llm_client=None)
        await integrator.integrate(
            code_modules=code_modules,
            integration_plan="Assemble all modules and verify integration.",
        )

        # 7. Build ForgeOutput
        total_tokens = sum(o.tokens_used for o in agent_outputs)
        total_retries = sum(o.retry_count for o in agent_outputs)

        forge_output = ForgeOutput(
            code_modules=code_modules,
            test_results={"all_tests": test_output.success},
            review_verdict=review_result.verdict,
            review_comments=review_result.comments,
            quality_score=review_result.score,
            total_tokens_used=total_tokens,
            total_retries=total_retries,
            topology_used=task_graph.topology,
            agent_outputs=agent_outputs,
        )

        state.forge_output = forge_output
        return state

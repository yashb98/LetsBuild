"""Integration tests for the full Code Forge pipeline.

Tests the end-to-end flow: ProjectSpec -> Planner -> Executor -> Tester ->
Reviewer -> Integrator, all using heuristic fallbacks (no LLM calls).
"""

from __future__ import annotations

import pytest

from letsbuild.forge.agents.integrator import IntegratorAgent
from letsbuild.forge.agents.planner import PlannerAgent
from letsbuild.forge.agents.reviewer import ReviewerAgent, ReviewResult
from letsbuild.forge.agents.tester import TesterAgent
from letsbuild.forge.context import ContextManager
from letsbuild.forge.executor import ForgeExecutor
from letsbuild.forge.retry import RetryHandler
from letsbuild.forge.tool_scoping import ToolScopingEnforcer
from letsbuild.forge.topology import TopologySelector
from letsbuild.hooks.post_code_gen import PostCodeGenerationHook
from letsbuild.models.architect_models import (
    ADR,
    ADRStatus,
    FeatureSpec,
    FileTreeNode,
    ProjectSpec,
    SandboxValidationCommand,
    SandboxValidationPlan,
)
from letsbuild.models.forge_models import (
    AgentOutput,
    AgentRole,
    CodeModule,
    ForgeOutput,
    ReviewVerdict,
    SwarmTopology,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_project_spec(
    *,
    num_features: int = 4,
    has_deps: bool = False,
) -> ProjectSpec:
    """Build a minimal valid ProjectSpec with the given number of features."""
    features: list[FeatureSpec] = []
    for i in range(num_features):
        deps: list[str] = []
        if has_deps and i > 0:
            deps = [features[i - 1].feature_name]
        features.append(
            FeatureSpec(
                feature_name=f"feature_{i}",
                description=f"Implements feature number {i}",
                module_path=f"src/feature_{i}.py",
                dependencies=deps,
                estimated_complexity=3,
                acceptance_criteria=[f"Feature {i} works"],
            )
        )

    return ProjectSpec(
        project_name="test-forge-project",
        one_liner="A test project for forge integration tests.",
        tech_stack=["python", "fastapi"],
        file_tree=[
            FileTreeNode(path="src/", is_directory=True, description="Source code"),
            FileTreeNode(path="tests/", is_directory=True, description="Tests"),
        ],
        feature_specs=features,
        sandbox_validation_plan=SandboxValidationPlan(
            commands=[
                SandboxValidationCommand(
                    command="pip install -e .",
                    description="Install project",
                ),
                SandboxValidationCommand(
                    command="pytest tests/ -v",
                    description="Run tests",
                ),
                SandboxValidationCommand(
                    command="ruff check .",
                    description="Lint check",
                ),
            ],
        ),
        adr_list=[
            ADR(
                title="Use FastAPI",
                status=ADRStatus.ACCEPTED,
                context="Need a modern Python web framework.",
                decision="Use FastAPI for the REST API layer.",
                consequences="Async-first, Pydantic integration.",
            ),
        ],
        skill_name="fullstack",
        complexity_score=5.0,
        estimated_loc=500,
        seniority_target="senior",
    )


def _make_code_modules(count: int = 3) -> list[CodeModule]:
    """Build sample CodeModule instances for testing."""
    modules: list[CodeModule] = []
    for i in range(count):
        modules.append(
            CodeModule(
                module_path=f"src/feature_{i}.py",
                content=f"# Auto-generated module for feature_{i}\ndef run():\n    return {i}\n",
                language="python",
                loc=3,
            )
        )
    return modules


# ------------------------------------------------------------------
# Test 1: Full forge end-to-end with heuristic fallbacks
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forge_end_to_end_heuristic() -> None:
    """Full forge pipeline: plan -> execute -> test -> review -> integrate.

    All agents use heuristic fallbacks (no LLM client).
    Verifies ForgeOutput has code_modules, review_verdict, and quality_score.
    """
    spec = _make_project_spec()

    # 1. Plan
    planner = PlannerAgent(llm_client=None)
    task_graph = await planner.plan(spec)
    assert len(task_graph.tasks) == len(spec.feature_specs)

    # 2. Execute (code generation)
    executor = ForgeExecutor(llm_client=None)
    agent_outputs = await executor.execute_tasks(task_graph, project_context="Test context")
    assert len(agent_outputs) == len(task_graph.tasks)
    assert all(o.success for o in agent_outputs)

    # Collect code modules
    code_modules: list[CodeModule] = []
    for output in agent_outputs:
        code_modules.extend(output.output_modules)
    assert len(code_modules) > 0

    # 3. Test
    tester = TesterAgent(llm_client=None)
    test_output = await tester.test(code_modules, test_plan="Run all tests")
    assert test_output.success

    # 4. Review
    reviewer = ReviewerAgent(llm_client=None)
    review_result = await reviewer.review(
        code_modules=code_modules,
        project_spec_summary="Test project with 4 features",
    )
    assert isinstance(review_result, ReviewResult)
    assert review_result.verdict in (ReviewVerdict.PASS, ReviewVerdict.PASS_WITH_SUGGESTIONS)
    assert review_result.score > 0.0

    # 5. Integrate
    integrator = IntegratorAgent(llm_client=None)
    integration_output = await integrator.integrate(
        code_modules=code_modules,
        integration_plan="Combine all modules",
    )
    assert integration_output.success
    assert len(integration_output.output_modules) == len(code_modules)

    # Build ForgeOutput
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

    assert len(forge_output.code_modules) > 0
    assert forge_output.review_verdict in (ReviewVerdict.PASS, ReviewVerdict.PASS_WITH_SUGGESTIONS)
    assert forge_output.quality_score > 0.0


# ------------------------------------------------------------------
# Test 2: Planner to executor flow
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forge_planner_to_executor() -> None:
    """Plan tasks from ProjectSpec, execute them, verify all completed."""
    spec = _make_project_spec(num_features=3)

    planner = PlannerAgent(llm_client=None)
    task_graph = await planner.plan(spec)

    executor = ForgeExecutor(llm_client=None)
    results = await executor.execute_tasks(task_graph, project_context="Integration test")

    assert len(results) == 3
    for result in results:
        assert result.success is True
        assert result.agent_role == AgentRole.CODER
        assert len(result.output_modules) > 0


# ------------------------------------------------------------------
# Test 3: Topology selection for different project specs
# ------------------------------------------------------------------


def test_forge_topology_selection() -> None:
    """Verify TopologySelector picks the right topology for various project shapes."""
    selector = TopologySelector()

    # <= 3 features -> SEQUENTIAL
    small_spec = _make_project_spec(num_features=2)
    assert selector.select(small_spec) == SwarmTopology.SEQUENTIAL

    # 4 features, no deps -> HIERARCHICAL
    medium_spec = _make_project_spec(num_features=5, has_deps=False)
    assert selector.select(medium_spec) == SwarmTopology.HIERARCHICAL

    # 4 features, with deps -> MESH
    dep_spec = _make_project_spec(num_features=5, has_deps=True)
    assert selector.select(dep_spec) == SwarmTopology.MESH

    # > 10 features -> RING
    large_spec = _make_project_spec(num_features=12)
    assert selector.select(large_spec) == SwarmTopology.RING


# ------------------------------------------------------------------
# Test 4: Tool scoping enforcement
# ------------------------------------------------------------------


def test_forge_tool_scoping_enforcement() -> None:
    """Verify each agent only has allowed tools per AGENT_TOOL_SCOPES."""
    enforcer = ToolScopingEnforcer()

    # Planner: read_file, list_directory only
    planner = PlannerAgent(llm_client=None)
    planner_tools = [str(t["name"]) for t in planner.tools()]
    violations = enforcer.validate_tools(AgentRole.PLANNER, planner_tools)
    assert violations == [], f"Planner has unauthorized tools: {violations}"

    # Tester: read_file, bash_execute, write_file
    tester = TesterAgent(llm_client=None)
    tester_tools = [str(t["name"]) for t in tester.tools()]
    violations = enforcer.validate_tools(AgentRole.TESTER, tester_tools)
    assert violations == [], f"Tester has unauthorized tools: {violations}"

    # Reviewer: read_file, list_directory only
    reviewer = ReviewerAgent(llm_client=None)
    reviewer_tools = [str(t["name"]) for t in reviewer.tools()]
    violations = enforcer.validate_tools(AgentRole.REVIEWER, reviewer_tools)
    assert violations == [], f"Reviewer has unauthorized tools: {violations}"

    # Integrator: read_file, write_file, bash_execute, docker_build
    integrator = IntegratorAgent(llm_client=None)
    integrator_tools = [str(t["name"]) for t in integrator.tools()]
    violations = enforcer.validate_tools(AgentRole.INTEGRATOR, integrator_tools)
    assert violations == [], f"Integrator has unauthorized tools: {violations}"

    # Verify enforcement raises on illegal tool
    with pytest.raises(ValueError, match="not allowed"):
        enforcer.enforce(AgentRole.PLANNER, ["read_file", "write_file"])


# ------------------------------------------------------------------
# Test 5: Retry integration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forge_retry_integration() -> None:
    """Simulate test failure -> retry -> success via RetryHandler."""
    from letsbuild.models.forge_models import Task
    from letsbuild.models.shared import ErrorCategory, StructuredError

    handler = RetryHandler(max_retries=3)
    call_count = 0

    task = Task(
        task_id="retry-test-001",
        module_name="src/buggy.py",
        description="Fix the buggy module",
        estimated_complexity=3,
    )

    async def _coder_fn(t: Task, retry_ctx: str) -> AgentOutput:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            # First attempt fails
            return AgentOutput(
                agent_role=AgentRole.CODER,
                task_id=t.task_id,
                success=False,
                output_modules=[],
                error=StructuredError(
                    error_category=ErrorCategory.TRANSIENT,
                    is_retryable=True,
                    message="Test assertion failed: expected 42, got 0",
                ),
                tokens_used=100,
                execution_time_seconds=1.0,
            )
        # Second attempt succeeds
        return AgentOutput(
            agent_role=AgentRole.CODER,
            task_id=t.task_id,
            success=True,
            output_modules=[
                CodeModule(
                    module_path="src/buggy.py",
                    content="def answer(): return 42\n",
                    language="python",
                    loc=1,
                ),
            ],
            tokens_used=80,
            execution_time_seconds=0.5,
        )

    result = await handler.retry_with_feedback(
        task=task,
        error_context="AssertionError: expected 42, got 0",
        coder_fn=_coder_fn,
    )

    assert result.success is True
    assert call_count == 2


# ------------------------------------------------------------------
# Test 6: Reviewer independence (no coder context)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forge_review_independent() -> None:
    """Verify the reviewer gets no coder context -- only code and spec summary."""
    reviewer = ReviewerAgent(llm_client=None)

    code_modules = _make_code_modules(2)
    review_result = await reviewer.review(
        code_modules=code_modules,
        project_spec_summary="Simple Python project with 2 modules",
        quality_checklist=["Has docstrings", "Has type hints"],
    )

    # Reviewer should produce a valid result without any coder history
    assert isinstance(review_result, ReviewResult)
    assert review_result.score > 0.0
    assert review_result.verdict in (
        ReviewVerdict.PASS,
        ReviewVerdict.PASS_WITH_SUGGESTIONS,
        ReviewVerdict.FAIL,
    )

    # Reviewer tools should be read-only
    reviewer_tool_names = [str(t["name"]) for t in reviewer.tools()]
    assert "write_file" not in reviewer_tool_names
    assert "bash_execute" not in reviewer_tool_names


# ------------------------------------------------------------------
# Test 7: Context trimming
# ------------------------------------------------------------------


def test_forge_context_trimming() -> None:
    """Generate verbose output, verify trimming keeps it within budget."""
    ctx_mgr = ContextManager(max_context_chars=100_000)

    # Verbose tool output (10,000 chars)
    verbose_output = "x" * 10_000
    trimmed = ctx_mgr.trim_tool_output(verbose_output, max_chars=200)
    assert len(trimmed) < len(verbose_output)
    assert "trimmed" in trimmed

    # Short output should be unchanged
    short_output = "Hello, world!"
    assert ctx_mgr.trim_tool_output(short_output, max_chars=200) == short_output

    # Conversation compression
    messages: list[dict[str, object]] = [
        {"role": "user", "content": f"Message {i}"} for i in range(20)
    ]
    compressed = ctx_mgr.compress_conversation(messages, keep_last_n=5)
    assert len(compressed) < len(messages)
    # First message should be the compressed summary
    first_content = str(compressed[0]["content"])
    assert "Compressed context" in first_content


# ------------------------------------------------------------------
# Test 8: PostCodeGen hook integration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_code_gen_hook_integration() -> None:
    """Generate code, run PostCodeGeneration hook, verify no secrets detected."""
    hook = PostCodeGenerationHook()

    clean_modules = _make_code_modules(3)
    result = await hook.run(clean_modules)

    assert result.modules_scanned == 3
    assert result.has_secrets is False
    assert result.secrets_found == []
    assert "generator" in result.metadata_tags

    # Now test with a module containing a secret
    secret_module = CodeModule(
        module_path="src/config.py",
        content='API_KEY = "sk-ant-abc123XYZ-thisisafakesecretkey"',
        language="python",
        loc=1,
    )
    result_with_secret = await hook.run([secret_module])

    assert result_with_secret.has_secrets is True
    assert len(result_with_secret.secrets_found) >= 1

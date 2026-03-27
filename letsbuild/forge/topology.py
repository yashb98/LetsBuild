"""Topology selector — chooses the agent swarm topology based on project characteristics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from letsbuild.models.forge_models import SwarmTopology, Task

if TYPE_CHECKING:
    from letsbuild.models.architect_models import ProjectSpec

logger = structlog.get_logger()

_SEQUENTIAL_THRESHOLD = 3
_RING_THRESHOLD = 10


class TopologySelector:
    """Select the appropriate swarm topology for a project and compute execution order.

    Topology rules (in priority order):

    1. If the skill config declares an explicit topology, use it.
    2. If the project has <= 3 features, use SEQUENTIAL.
    3. If all features are independent (no cross-dependencies), use HIERARCHICAL.
    4. If features have cross-dependencies, use MESH.
    5. If the project has > 10 features, use RING.
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(self, project_spec: ProjectSpec) -> SwarmTopology:
        """Select the best topology for *project_spec*."""
        # 1. Explicit topology from skill config frontmatter.
        spec_dict = project_spec.model_dump()
        skill_topology = spec_dict.get("skill_topology")
        if skill_topology is not None:
            try:
                topology = SwarmTopology(skill_topology)
                self._log.info(
                    "topology.from_skill_config",
                    topology=topology,
                    project=project_spec.project_name,
                )
                return topology
            except ValueError:
                self._log.warning(
                    "topology.invalid_skill_topology",
                    value=skill_topology,
                )

        features = project_spec.feature_specs
        num_features = len(features)

        # 5. Large projects (> 10 features) → RING.
        if num_features > _RING_THRESHOLD:
            self._log.info(
                "topology.ring",
                num_features=num_features,
                project=project_spec.project_name,
            )
            return SwarmTopology.RING

        # 2. Few features (≤ 3) → SEQUENTIAL.
        if num_features <= _SEQUENTIAL_THRESHOLD:
            self._log.info(
                "topology.sequential",
                num_features=num_features,
                project=project_spec.project_name,
            )
            return SwarmTopology.SEQUENTIAL

        # 3/4. Check for cross-dependencies.
        has_cross_deps = any(len(f.dependencies) > 0 for f in features)

        if has_cross_deps:
            self._log.info(
                "topology.mesh",
                num_features=num_features,
                project=project_spec.project_name,
            )
            return SwarmTopology.MESH

        # Default: HIERARCHICAL (all features independent).
        self._log.info(
            "topology.hierarchical",
            num_features=num_features,
            project=project_spec.project_name,
        )
        return SwarmTopology.HIERARCHICAL

    def get_execution_order(
        self,
        topology: SwarmTopology,
        tasks: list[Task],
    ) -> list[list[Task]]:
        """Return batches of tasks to execute for the given *topology*.

        Each inner list represents a batch that can run concurrently.
        Batches are executed sequentially.

        - HIERARCHICAL: group by assigned agent role order
          (planner -> coder -> tester -> reviewer -> integrator).
        - SEQUENTIAL: each task in its own batch.
        - MESH: all tasks in a single batch (maximum parallelism).
        - RING: rotate through tasks one at a time (same as sequential for
          scheduling; the ring-pass validation is handled at the agent level).
        """
        if not tasks:
            return []

        if topology == SwarmTopology.SEQUENTIAL:
            return [[t] for t in tasks]

        if topology == SwarmTopology.MESH:
            return [list(tasks)]

        if topology == SwarmTopology.RING:
            return [[t] for t in tasks]

        # HIERARCHICAL — group by agent role in pipeline order.
        role_order = ["planner", "coder", "tester", "reviewer", "integrator"]
        batches: dict[str, list[Task]] = {role: [] for role in role_order}

        for task in tasks:
            role_key = task.assigned_agent.value if task.assigned_agent else "coder"
            if role_key in batches:
                batches[role_key].append(task)
            else:
                batches["coder"].append(task)

        return [batch for batch in batches.values() if batch]

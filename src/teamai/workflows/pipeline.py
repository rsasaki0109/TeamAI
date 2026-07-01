from __future__ import annotations

from uuid import UUID

from teamai.agents.critic import CriticAgent
from teamai.agents.finalizer import FinalizerAgent
from teamai.agents.specialist import SpecialistAgent
from teamai.core.budgets import Budget
from teamai.core.domain import (
    AgentDescriptor,
    Artifact,
    ModelUsage,
    Plan,
    PlannedTask,
)
from teamai.core.events import EventEmitter
from teamai.core.protocols import ArtifactStore
from teamai.core.routing import CapabilityRoutingPolicy
from teamai.tools.broker import ToolBroker
from teamai.workflows.task_execution import ReviewedTaskExecutor


class PipelineWorkflow:
    def __init__(
        self,
        *,
        run_id: UUID,
        specialists: dict[str, SpecialistAgent],
        critic: CriticAgent,
        finalizer: FinalizerAgent,
        budget: Budget,
        event_emitter: EventEmitter,
        artifact_store: ArtifactStore,
        tool_broker: ToolBroker,
    ) -> None:
        self._specialists = specialists
        self._critic = critic
        self._finalizer = finalizer
        self._budget = budget
        self._events = event_emitter
        self._router = CapabilityRoutingPolicy()
        self._task_executor = ReviewedTaskExecutor(
            run_id=run_id,
            budget=budget,
            event_emitter=event_emitter,
            artifact_store=artifact_store,
            tool_broker=tool_broker,
        )
        self.usage = ModelUsage()

    async def run(self, goal: str) -> tuple[str, list[Artifact]]:
        plan = Plan(
            summary=f"Pipeline task for: {goal}",
            tasks=[
                PlannedTask(
                    id="task_1",
                    objective=goal,
                    required_capabilities=set(),
                    dependencies=[],
                    acceptance_criteria=["The requested goal is addressed."],
                    expected_artifact_type="text",
                )
            ],
            final_acceptance_criteria=["A final result is produced from reviewed artifacts."],
        )
        task = plan.tasks[0].to_task()

        self._budget.check_task_count(1)
        await self._events.emit("pipeline.started", actor="conductor")
        await self._events.emit("task.ready", actor="conductor", task_id=task.id)
        assigned = await self._router.select_agent(task, self._specialist_descriptors())
        await self._events.emit(
            "task.assigned",
            actor="conductor",
            task_id=task.id,
            payload={"agent": assigned},
        )

        artifact, reviews, usage = await self._task_executor.execute(
            goal=goal,
            task=task,
            specialist=self._specialists[assigned],
            critic=self._critic,
            dependency_artifacts=[],
        )
        self._add_usage(usage)

        final_output, usage = await self._finalizer.finalize(
            goal=goal,
            plan=plan,
            artifacts=[artifact],
            reviews=reviews,
        )
        self._add_usage(usage)
        await self._events.emit("pipeline.completed", actor="conductor")
        return final_output, [artifact]

    def _specialist_descriptors(self) -> list[AgentDescriptor]:
        return [
            AgentDescriptor(
                name=name,
                kind=agent.config.kind,
                capabilities=set(agent.config.capabilities),
            )
            for name, agent in sorted(self._specialists.items())
        ]

    def _add_usage(self, usage: ModelUsage) -> None:
        self.usage.add(usage)

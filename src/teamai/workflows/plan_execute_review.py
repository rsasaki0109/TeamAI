from __future__ import annotations

from uuid import UUID

from teamai.agents.critic import CriticAgent
from teamai.agents.finalizer import FinalizerAgent
from teamai.agents.planner import PlannerAgent
from teamai.agents.specialist import SpecialistAgent
from teamai.core.budgets import Budget
from teamai.core.domain import (
    AgentDescriptor,
    ApprovalRequest,
    Artifact,
    ModelUsage,
    Plan,
    RiskLevel,
    Task,
)
from teamai.core.errors import ApprovalRejectedError
from teamai.core.events import EventEmitter
from teamai.core.protocols import ApprovalProvider, ArtifactStore
from teamai.core.routing import CapabilityRoutingPolicy
from teamai.telemetry.redaction import redact
from teamai.tools.broker import ToolBroker
from teamai.workflows.task_execution import ReviewedTaskExecutor
from teamai.workflows.validation import validate_plan


class PlanExecuteReviewWorkflow:
    def __init__(
        self,
        *,
        run_id: UUID,
        planner: PlannerAgent,
        specialists: dict[str, SpecialistAgent],
        critic: CriticAgent,
        finalizer: FinalizerAgent,
        budget: Budget,
        event_emitter: EventEmitter,
        artifact_store: ArtifactStore,
        tool_broker: ToolBroker,
        approval_provider: ApprovalProvider,
        require_plan_approval: bool,
        tool_names: list[str],
    ) -> None:
        self._run_id = run_id
        self._planner = planner
        self._specialists = specialists
        self._critic = critic
        self._finalizer = finalizer
        self._budget = budget
        self._events = event_emitter
        self._artifact_store = artifact_store
        self._tool_broker = tool_broker
        self._approval_provider = approval_provider
        self._requires_plan_approval = require_plan_approval
        self._tool_names = tool_names
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
        await self._events.emit("plan.requested", actor="conductor")
        plan, usage = await self._planner.create_plan(
            goal=goal,
            available_agents=self._specialist_descriptors(),
            tool_names=self._tool_names,
        )
        self._add_usage(usage)
        await self._events.emit(
            "plan.created",
            actor=self._planner.name,
            payload={"task_count": len(plan.tasks), "summary": plan.summary},
        )
        ordered_ids = validate_plan(plan, self._budget, self._specialist_descriptors())
        await self._events.emit("plan.validated", actor="conductor", payload={"tasks": ordered_ids})
        await self._approve_plan(plan)

        tasks = {planned.id: planned.to_task() for planned in plan.tasks}
        artifacts_by_task: dict[str, Artifact] = {}
        all_reviews = []

        for task_id in ordered_ids:
            task = tasks[task_id]
            await self._approve_high_risk_task(task)
            await self._events.emit("task.ready", actor="conductor", task_id=task.id)
            assigned = await self._router.select_agent(task, self._specialist_descriptors())
            await self._events.emit(
                "task.assigned",
                actor="conductor",
                task_id=task.id,
                payload={"agent": assigned},
            )
            specialist = self._specialists[assigned]
            dependency_artifacts = [
                artifacts_by_task[dependency] for dependency in task.dependencies
            ]
            artifact, reviews, usage = await self._task_executor.execute(
                goal=goal,
                task=task,
                specialist=specialist,
                critic=self._critic,
                dependency_artifacts=dependency_artifacts,
            )
            self._add_usage(usage)
            all_reviews.extend(reviews)
            artifacts_by_task[task.id] = artifact

        artifacts = [artifacts_by_task[task_id] for task_id in ordered_ids]
        final_output, usage = await self._finalizer.finalize(
            goal=goal,
            plan=plan,
            artifacts=artifacts,
            reviews=all_reviews,
        )
        self._add_usage(usage)
        return final_output, artifacts

    def _specialist_descriptors(self) -> list[AgentDescriptor]:
        return [
            AgentDescriptor(
                name=name,
                kind=agent.config.kind,
                capabilities=set(agent.config.capabilities),
            )
            for name, agent in sorted(self._specialists.items())
        ]

    async def _approve_plan(self, plan: Plan) -> None:
        if not self._requires_plan_approval:
            return
        request = ApprovalRequest(
            run_id=self._run_id,
            reason="Teamfile requires plan approval before execution",
            action="plan.execute",
            redacted_arguments=redact(plan.model_dump(mode="json")),
            risk=RiskLevel.MEDIUM,
            preview=f"{plan.summary}\nTasks: {len(plan.tasks)}",
        )
        await self._events.emit(
            "approval.requested",
            actor="conductor",
            payload=redact(request.model_dump(mode="json")),
        )
        decision = await self._approval_provider.request(request)
        await self._events.emit(
            "approval.completed",
            actor="conductor",
            payload=redact(decision.model_dump(mode="json")),
        )
        if not decision.approved:
            raise ApprovalRejectedError(decision.comment or "approval rejected for plan")

    async def _approve_high_risk_task(self, task: Task) -> None:
        if task.risk != RiskLevel.HIGH:
            return
        request = ApprovalRequest(
            run_id=self._run_id,
            reason="task is marked high risk by the plan",
            action="task.execute",
            redacted_arguments=redact(task.model_dump(mode="json")),
            risk=RiskLevel.HIGH,
            preview=f"Task {task.id}: {task.objective}",
        )
        await self._events.emit(
            "approval.requested",
            actor="conductor",
            task_id=task.id,
            payload=redact(request.model_dump(mode="json")),
        )
        decision = await self._approval_provider.request(request)
        await self._events.emit(
            "approval.completed",
            actor="conductor",
            task_id=task.id,
            payload=redact(decision.model_dump(mode="json")),
        )
        if not decision.approved:
            raise ApprovalRejectedError(
                decision.comment or f"approval rejected for high-risk task {task.id}"
            )

    def _add_usage(self, usage: ModelUsage) -> None:
        self.usage.add(usage)

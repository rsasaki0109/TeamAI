from __future__ import annotations

from uuid import UUID

from teamai.agents.critic import CriticAgent
from teamai.agents.specialist import SpecialistAgent
from teamai.core.budgets import Budget
from teamai.core.domain import (
    Artifact,
    ModelUsage,
    Review,
    Task,
    ToolCall,
    ToolObservation,
    WorkProduct,
)
from teamai.core.errors import TeamAIError
from teamai.core.events import EventEmitter
from teamai.core.protocols import ArtifactStore
from teamai.telemetry.redaction import redact
from teamai.tools.broker import ToolBroker


class ReviewedTaskExecutor:
    def __init__(
        self,
        *,
        run_id: UUID,
        budget: Budget,
        event_emitter: EventEmitter,
        artifact_store: ArtifactStore,
        tool_broker: ToolBroker,
    ) -> None:
        self._run_id = run_id
        self._budget = budget
        self._events = event_emitter
        self._artifact_store = artifact_store
        self._tool_broker = tool_broker

    async def execute(
        self,
        *,
        goal: str,
        task: Task,
        specialist: SpecialistAgent,
        critic: CriticAgent,
        dependency_artifacts: list[Artifact],
    ) -> tuple[Artifact, list[Review], ModelUsage]:
        reviews: list[Review] = []
        usage = ModelUsage()
        revision_feedback: list[str] = []

        for revision in range(self._budget.limits.max_revisions_per_task + 1):
            task.revision = revision
            tool_results: list[ToolObservation] = []
            await self._events.emit("agent.started", actor=specialist.name, task_id=task.id)
            product: WorkProduct | None = None

            while True:
                product, call_usage = await specialist.run_task(
                    goal=goal,
                    task=task,
                    dependency_artifacts=dependency_artifacts,
                    revision_feedback=revision_feedback,
                    tool_results=tool_results,
                )
                usage.add(call_usage)
                if not product.tool_requests:
                    break
                tool_results.extend(
                    await self._execute_tool_requests(
                        specialist=specialist,
                        task_id=task.id,
                        requests=product.tool_requests,
                    )
                )

            if product is None:
                raise TeamAIError(f"task {task.id} produced no work product")
            artifact = await self._create_artifact(
                task=task,
                specialist=specialist,
                product=product,
                tool_results=tool_results,
                revision=revision,
                )

            await self._events.emit("review.requested", actor="conductor", task_id=task.id)
            review, call_usage = await critic.review(goal=goal, task=task, artifact=artifact)
            usage.add(call_usage)
            reviews.append(review)
            await self._events.emit(
                "review.completed",
                actor=critic.name,
                task_id=task.id,
                payload=review.model_dump(mode="json"),
            )

            if review.decision == "pass":
                await self._events.emit("task.completed", actor="conductor", task_id=task.id)
                return artifact, reviews, usage
            if review.decision == "fail":
                raise TeamAIError(f"task {task.id} failed review")
            if revision >= self._budget.limits.max_revisions_per_task:
                raise TeamAIError(f"task {task.id} exceeded revision limit")
            revision_feedback = review.revision_instructions or review.issues
            await self._events.emit(
                "task.revision_requested",
                actor=critic.name,
                task_id=task.id,
                payload={"next_revision": revision + 1},
            )

        raise TeamAIError(f"task {task.id} exceeded revision limit")

    async def _create_artifact(
        self,
        *,
        task: Task,
        specialist: SpecialistAgent,
        product: WorkProduct,
        tool_results: list[ToolObservation],
        revision: int,
    ) -> Artifact:
        artifact = Artifact(
            run_id=self._run_id,
            task_id=task.id,
            type=task.expected_artifact_type,
            summary=product.summary,
            content=product.content,
            metadata={
                "agent": specialist.name,
                "produced_files": product.produced_files,
                "evidence": product.evidence,
                "tool_results": [
                    redact(observation.model_dump(mode="json"))
                    for observation in tool_results
                ],
                "confidence": product.confidence,
                "revision": revision,
            },
        )
        await self._artifact_store.save_artifact(artifact)
        await self._events.emit(
            "artifact.created",
            actor=specialist.name,
            task_id=task.id,
            payload={"artifact_id": str(artifact.id), "summary": artifact.summary},
        )
        return artifact

    async def _execute_tool_requests(
        self,
        *,
        specialist: SpecialistAgent,
        task_id: str,
        requests: list[ToolCall],
    ) -> list[ToolObservation]:
        observations: list[ToolObservation] = []
        allowed_tools = set(specialist.config.tools)
        for request in requests:
            result = await self._tool_broker.execute(
                request.name,
                request.arguments,
                actor=specialist.name,
                task_id=task_id,
                allowed_tools=allowed_tools,
            )
            observations.append(
                ToolObservation(
                    name=request.name,
                    arguments=dict(request.arguments),
                    output=result.output,
                )
            )
        return observations

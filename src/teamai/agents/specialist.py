from __future__ import annotations

from teamai.agents.base import LLMAgent
from teamai.core.domain import Artifact, ModelUsage, Task, ToolObservation, WorkProduct


class SpecialistAgent(LLMAgent):
    async def run_task(
        self,
        *,
        goal: str,
        task: Task,
        dependency_artifacts: list[Artifact],
        revision_feedback: list[str],
        tool_results: list[ToolObservation],
    ) -> tuple[WorkProduct, ModelUsage]:
        system = (
            "You are a specialist agent. Complete the assigned task and return only JSON "
            "matching the WorkProduct schema. If you need a permitted tool before producing "
            "the final content, include tool_requests and keep the request precise."
        )
        if self.config.instructions:
            system = f"{system}\n\nAdditional instructions:\n{self.config.instructions}"
        dependency_payload = [
            artifact.model_dump(mode="json") for artifact in dependency_artifacts
        ]
        user = (
            f"Goal:\n{goal}\n\n"
            f"Task:\n{task.model_dump(mode='json')}\n\n"
            f"Dependency artifacts:\n{dependency_payload}\n\n"
            f"Revision feedback:\n{revision_feedback}\n\n"
            f"Allowed tools:\n{self.config.tools}\n\n"
            f"Tool results:\n{[result.model_dump(mode='json') for result in tool_results]}"
        )
        return await self._complete_structured(
            system=system,
            user=user,
            output_schema="WorkProduct",
            metadata={
                "goal": goal,
                "task": task.model_dump(mode="json"),
                "dependency_artifacts": dependency_payload,
                "revision_feedback": revision_feedback,
                "allowed_tools": self.config.tools,
                "tool_results": [
                    result.model_dump(mode="json") for result in tool_results
                ],
            },
            model_type=WorkProduct,
        )

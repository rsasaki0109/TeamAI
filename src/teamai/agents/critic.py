from __future__ import annotations

from teamai.agents.base import LLMAgent
from teamai.core.domain import Artifact, ModelUsage, Review, Task


class CriticAgent(LLMAgent):
    async def review(
        self,
        *,
        goal: str,
        task: Task,
        artifact: Artifact,
    ) -> tuple[Review, ModelUsage]:
        system = (
            "You are a critic agent. Review the artifact against the task acceptance criteria. "
            "Return only JSON matching the Review schema."
        )
        if self.config.instructions:
            system = f"{system}\n\nAdditional instructions:\n{self.config.instructions}"
        user = (
            f"Goal:\n{goal}\n\n"
            f"Task:\n{task.model_dump(mode='json')}\n\n"
            f"Artifact:\n{artifact.model_dump(mode='json')}"
        )
        return await self._complete_structured(
            system=system,
            user=user,
            output_schema="Review",
            metadata={
                "goal": goal,
                "task": task.model_dump(mode="json"),
                "artifact": artifact.model_dump(mode="json"),
            },
            model_type=Review,
        )

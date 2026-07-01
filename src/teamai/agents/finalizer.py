from __future__ import annotations

from teamai.agents.base import LLMAgent
from teamai.core.domain import Artifact, FinalOutput, ModelUsage, Plan, Review


class FinalizerAgent(LLMAgent):
    async def finalize(
        self,
        *,
        goal: str,
        plan: Plan,
        artifacts: list[Artifact],
        reviews: list[Review],
    ) -> tuple[str, ModelUsage]:
        system = (
            "You are a finalizer agent. Produce the final user-facing result. "
            "Return only JSON matching the FinalOutput schema."
        )
        if self.config.instructions:
            system = f"{system}\n\nAdditional instructions:\n{self.config.instructions}"
        user = (
            f"Goal:\n{goal}\n\n"
            f"Plan:\n{plan.model_dump(mode='json')}\n\n"
            f"Artifacts:\n{[artifact.model_dump(mode='json') for artifact in artifacts]}\n\n"
            f"Reviews:\n{[review.model_dump(mode='json') for review in reviews]}"
        )
        output, tokens = await self._complete_structured(
            system=system,
            user=user,
            output_schema="FinalOutput",
            metadata={
                "goal": goal,
                "plan": plan.model_dump(mode="json"),
                "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
                "reviews": [review.model_dump(mode="json") for review in reviews],
            },
            model_type=FinalOutput,
        )
        return output.final_output, tokens

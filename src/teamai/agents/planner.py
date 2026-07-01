from __future__ import annotations

from teamai.agents.base import LLMAgent
from teamai.core.domain import AgentDescriptor, ModelUsage, Plan


class PlannerAgent(LLMAgent):
    async def create_plan(
        self,
        *,
        goal: str,
        available_agents: list[AgentDescriptor],
        tool_names: list[str],
    ) -> tuple[Plan, ModelUsage]:
        system = (
            "You are the planner for a TeamAI run. Return only JSON matching the Plan schema. "
            "Plan tasks around capabilities, not specific agent names."
        )
        if self.config.instructions:
            system = f"{system}\n\nAdditional instructions:\n{self.config.instructions}"
        available_agent_payload = [
            agent.model_dump(mode="json") for agent in available_agents
        ]
        user = (
            f"Goal:\n{goal}\n\n"
            f"Available agents:\n{available_agent_payload}\n\n"
            f"Available tools:\n{tool_names}"
        )
        return await self._complete_structured(
            system=system,
            user=user,
            output_schema="Plan",
            metadata={
                "goal": goal,
                "available_agents": available_agent_payload,
                "tool_names": tool_names,
            },
            model_type=Plan,
        )

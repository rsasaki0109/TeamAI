from __future__ import annotations

from collections.abc import Sequence

from teamai.core.domain import AgentDescriptor, Task
from teamai.core.errors import RoutingError


class CapabilityRoutingPolicy:
    async def select_agent(self, task: Task, candidates: Sequence[AgentDescriptor]) -> str:
        eligible = [
            candidate
            for candidate in candidates
            if task.required_capabilities.issubset(candidate.capabilities)
        ]
        if not eligible:
            required = ", ".join(sorted(task.required_capabilities)) or "<none>"
            raise RoutingError(f"no specialist has required capabilities: {required}")
        eligible.sort(key=lambda candidate: (len(candidate.capabilities), candidate.name))
        return eligible[0].name

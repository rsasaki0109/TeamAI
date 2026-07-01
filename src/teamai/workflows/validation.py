from __future__ import annotations

from collections import defaultdict, deque

from teamai.core.budgets import Budget
from teamai.core.domain import AgentDescriptor, Plan
from teamai.core.errors import PlanValidationError


def validate_plan(plan: Plan, budget: Budget, specialists: list[AgentDescriptor]) -> list[str]:
    budget.check_task_count(len(plan.tasks))
    if not plan.tasks:
        raise PlanValidationError("plan must contain at least one task")
    task_ids = [task.id for task in plan.tasks]
    if len(task_ids) != len(set(task_ids)):
        raise PlanValidationError("task ids must be unique")
    known = set(task_ids)
    for task in plan.tasks:
        if not task.acceptance_criteria:
            raise PlanValidationError(f"task {task.id} has no acceptance criteria")
        for dependency in task.dependencies:
            if dependency not in known:
                raise PlanValidationError(f"task {task.id} depends on unknown task {dependency}")
        has_candidate = any(
            task.required_capabilities.issubset(agent.capabilities)
            for agent in specialists
        )
        if not has_candidate:
            required = ", ".join(sorted(task.required_capabilities)) or "<none>"
            raise PlanValidationError(f"no specialist satisfies task {task.id}: {required}")
    return topological_task_ids(plan)


def topological_task_ids(plan: Plan) -> list[str]:
    incoming: dict[str, int] = {task.id: 0 for task in plan.tasks}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for task in plan.tasks:
        for dependency in task.dependencies:
            incoming[task.id] += 1
            outgoing[dependency].append(task.id)
    queue = deque(sorted(task_id for task_id, count in incoming.items() if count == 0))
    ordered: list[str] = []
    while queue:
        task_id = queue.popleft()
        ordered.append(task_id)
        for child in sorted(outgoing[task_id]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    if len(ordered) != len(incoming):
        raise PlanValidationError("plan contains a dependency cycle")
    return ordered

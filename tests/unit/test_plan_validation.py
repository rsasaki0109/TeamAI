import pytest

from teamai.core.budgets import Budget, BudgetLimits
from teamai.core.domain import AgentDescriptor, AgentKind, Plan, PlannedTask
from teamai.core.errors import BudgetExceededError, PlanValidationError
from teamai.workflows.validation import validate_plan


def _budget(*, max_tasks: int = 4) -> Budget:
    return Budget(
        BudgetLimits(
            max_model_calls=10,
            max_tool_calls=10,
            max_tasks=max_tasks,
            max_revisions_per_task=1,
            max_runtime_seconds=60,
            max_output_tokens_per_call=1024,
            max_parallel_tasks=1,
        )
    )


def _specialists() -> list[AgentDescriptor]:
    return [
        AgentDescriptor(
            name="coder",
            kind=AgentKind.SPECIALIST,
            capabilities={"python", "testing"},
        )
    ]


def _task(
    task_id: str,
    *,
    dependencies: list[str] | None = None,
    capabilities: set[str] | None = None,
    criteria: list[str] | None = None,
) -> PlannedTask:
    return PlannedTask(
        id=task_id,
        objective=f"Do {task_id}",
        required_capabilities=capabilities or {"python"},
        dependencies=dependencies or [],
        acceptance_criteria=criteria if criteria is not None else ["Done"],
        expected_artifact_type="text",
    )


def _plan(tasks: list[PlannedTask]) -> Plan:
    return Plan(summary="Test plan", tasks=tasks, final_acceptance_criteria=["Done"])


def test_validate_plan_returns_topological_order() -> None:
    plan = _plan(
        [
            _task("inspect"),
            _task("implement", dependencies=["inspect"]),
            _task("test", dependencies=["implement"]),
        ]
    )

    assert validate_plan(plan, _budget(), _specialists()) == [
        "inspect",
        "implement",
        "test",
    ]


def test_validate_plan_rejects_duplicate_task_ids() -> None:
    plan = _plan([_task("same"), _task("same")])

    with pytest.raises(PlanValidationError, match="unique"):
        validate_plan(plan, _budget(), _specialists())


def test_validate_plan_rejects_unknown_dependency() -> None:
    plan = _plan([_task("implement", dependencies=["inspect"])])

    with pytest.raises(PlanValidationError, match="unknown task"):
        validate_plan(plan, _budget(), _specialists())


def test_validate_plan_rejects_dependency_cycle() -> None:
    plan = _plan(
        [
            _task("a", dependencies=["b"]),
            _task("b", dependencies=["a"]),
        ]
    )

    with pytest.raises(PlanValidationError, match="cycle"):
        validate_plan(plan, _budget(), _specialists())


def test_validate_plan_rejects_empty_acceptance_criteria() -> None:
    plan = _plan([_task("implement", criteria=[])])

    with pytest.raises(PlanValidationError, match="acceptance criteria"):
        validate_plan(plan, _budget(), _specialists())


def test_validate_plan_rejects_missing_capability() -> None:
    plan = _plan([_task("deploy", capabilities={"kubernetes"})])

    with pytest.raises(PlanValidationError, match="no specialist"):
        validate_plan(plan, _budget(), _specialists())


def test_validate_plan_rejects_task_count_over_budget() -> None:
    plan = _plan([_task("a"), _task("b")])

    with pytest.raises(BudgetExceededError, match="max_tasks"):
        validate_plan(plan, _budget(max_tasks=1), _specialists())

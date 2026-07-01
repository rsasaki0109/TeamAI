from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from teamai.core.errors import BudgetExceededError


@dataclass(frozen=True)
class BudgetLimits:
    max_model_calls: int
    max_tool_calls: int
    max_tasks: int
    max_revisions_per_task: int
    max_runtime_seconds: int
    max_output_tokens_per_call: int
    max_parallel_tasks: int


class Budget:
    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.model_calls = 0
        self.tool_calls = 0
        self.started_at = monotonic()

    def check_runtime(self) -> None:
        elapsed = monotonic() - self.started_at
        if elapsed > self.limits.max_runtime_seconds:
            raise BudgetExceededError("run exceeded max_runtime_seconds")

    def check_task_count(self, count: int) -> None:
        if count > self.limits.max_tasks:
            raise BudgetExceededError("plan exceeded max_tasks")

    def consume_model_call(self) -> None:
        self.check_runtime()
        self.model_calls += 1
        if self.model_calls > self.limits.max_model_calls:
            raise BudgetExceededError("run exceeded max_model_calls")

    def consume_tool_call(self) -> None:
        self.check_runtime()
        self.tool_calls += 1
        if self.tool_calls > self.limits.max_tool_calls:
            raise BudgetExceededError("run exceeded max_tool_calls")

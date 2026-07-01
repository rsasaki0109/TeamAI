from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from teamai.config.models import SecurityConfig
from teamai.core.budgets import Budget
from teamai.core.domain import ApprovalRequest, RiskLevel, SideEffect, ToolResult
from teamai.core.errors import ApprovalRejectedError, ToolExecutionError
from teamai.core.events import EventEmitter
from teamai.core.protocols import ApprovalProvider
from teamai.telemetry.redaction import approval_preview, redact
from teamai.tools.base import ToolRegistry


class ToolBroker:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        security: SecurityConfig,
        budget: Budget,
        approval_provider: ApprovalProvider,
        event_emitter: EventEmitter,
        run_id: UUID,
    ) -> None:
        self._registry = registry
        self._security = security
        self._budget = budget
        self._approval_provider = approval_provider
        self._events = event_emitter
        self._run_id = run_id

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, object],
        *,
        actor: str,
        task_id: str | None,
        allowed_tools: set[str],
    ) -> ToolResult:
        if name not in allowed_tools:
            raise ToolExecutionError(f"tool {name} is not allowed for agent {actor}")
        try:
            tool = self._registry.get(name)
        except KeyError as exc:
            raise ToolExecutionError(f"unknown tool: {name}") from exc
        self._budget.consume_tool_call()
        redacted_arguments = redact(dict(arguments))
        await self._events.emit(
            "tool.requested",
            actor=actor,
            task_id=task_id,
            payload={
                "tool": name,
                "arguments": redacted_arguments,
                "side_effect": tool.spec.side_effect.value,
            },
        )
        if self._requires_approval(name, tool.spec.side_effect):
            request = ApprovalRequest(
                run_id=self._run_id,
                reason=f"tool {name} has side effect {tool.spec.side_effect.value}",
                action=name,
                redacted_arguments=redacted_arguments,
                risk=RiskLevel.MEDIUM
                if tool.spec.side_effect in {SideEffect.WRITE, SideEffect.EXECUTE}
                else RiskLevel.LOW,
                preview=approval_preview(name, arguments),
            )
            await self._events.emit(
                "approval.requested",
                actor="conductor",
                task_id=task_id,
                payload=redact(request.model_dump(mode="json")),
            )
            decision = await self._approval_provider.request(request)
            await self._events.emit(
                "approval.completed",
                actor="conductor",
                task_id=task_id,
                payload=redact(decision.model_dump(mode="json")),
            )
            if not decision.approved:
                raise ApprovalRejectedError(decision.comment or f"approval rejected for {name}")
        try:
            result = await tool.execute(arguments)
        except Exception as exc:
            await self._events.emit(
                "tool.failed",
                actor=actor,
                task_id=task_id,
                payload={"tool": name, "error_type": type(exc).__name__, "error": str(exc)},
            )
            raise
        await self._events.emit(
            "tool.completed",
            actor=actor,
            task_id=task_id,
            payload={"tool": name, "output": redact(result.output)},
        )
        return result

    def _requires_approval(self, name: str, side_effect: SideEffect) -> bool:
        requirements = set(self._security.require_approval_for)
        return name in requirements or side_effect.value in requirements

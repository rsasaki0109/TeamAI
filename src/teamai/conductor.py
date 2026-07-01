from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from teamai.agents.critic import CriticAgent
from teamai.agents.finalizer import FinalizerAgent
from teamai.agents.planner import PlannerAgent
from teamai.agents.specialist import SpecialistAgent
from teamai.config.models import AgentConfig, TeamConfig
from teamai.core.budgets import Budget
from teamai.core.domain import AgentKind, Artifact, ModelUsage, RunResult
from teamai.core.events import EventEmitter
from teamai.core.protocols import ApprovalProvider, ModelClient, RunStore
from teamai.core.states import RunStatus
from teamai.providers.audit import AuditedModelClient
from teamai.tools.base import ToolRegistry
from teamai.tools.broker import ToolBroker


class _Workflow(Protocol):
    usage: ModelUsage

    async def run(self, goal: str) -> tuple[str, list[Artifact]]:
        raise NotImplementedError


class Conductor:
    def __init__(
        self,
        *,
        config: TeamConfig,
        model_clients: dict[str, ModelClient],
        store: RunStore,
        tool_registry: ToolRegistry,
        approval_provider: ApprovalProvider,
    ) -> None:
        self._config = config
        self._model_clients = model_clients
        self._store = store
        self._tool_registry = tool_registry
        self._approval_provider = approval_provider

    async def run(self, goal: str) -> RunResult:
        from teamai.workflows.pipeline import PipelineWorkflow
        from teamai.workflows.plan_execute_review import PlanExecuteReviewWorkflow

        run_id = uuid4()
        events = EventEmitter(run_id, self._store)
        budget = Budget(self._config.limits.to_budget_limits())
        audited_model_clients: dict[str, ModelClient] = {
            name: AuditedModelClient(name=name, wrapped=client, events=events)
            for name, client in self._model_clients.items()
        }
        tool_broker = ToolBroker(
            registry=self._tool_registry,
            security=self._config.security,
            budget=budget,
            approval_provider=self._approval_provider,
            event_emitter=events,
            run_id=run_id,
        )
        await events.emit(
            "run.created",
            actor="conductor",
            payload={"team": self._config.team.name},
        )
        await events.emit("run.started", actor="conductor", payload={"goal": goal})

        try:
            workflow: _Workflow
            specialists = self._build_specialists(audited_model_clients, events, budget)
            critic = self._build_critic(audited_model_clients, events, budget)
            finalizer = self._build_finalizer(audited_model_clients, events, budget)
            if self._config.workflow.strategy == "pipeline":
                workflow = PipelineWorkflow(
                    run_id=run_id,
                    specialists=specialists,
                    critic=critic,
                    finalizer=finalizer,
                    budget=budget,
                    event_emitter=events,
                    artifact_store=self._store,
                    tool_broker=tool_broker,
                )
            else:
                workflow = PlanExecuteReviewWorkflow(
                    run_id=run_id,
                    planner=self._build_planner(audited_model_clients, events, budget),
                    specialists=specialists,
                    critic=critic,
                    finalizer=finalizer,
                    budget=budget,
                    event_emitter=events,
                    artifact_store=self._store,
                    tool_broker=tool_broker,
                    approval_provider=self._approval_provider,
                    require_plan_approval=self._config.security.require_plan_approval,
                    tool_names=self._tool_registry.names(),
                )
            final_output, artifacts = await workflow.run(goal)
            result = RunResult(
                run_id=run_id,
                status=RunStatus.SUCCEEDED,
                final_output=final_output,
                artifacts=artifacts,
                usage=workflow.usage,
            )
            await events.emit(
                "run.completed",
                actor="conductor",
                payload={"status": result.status.value},
            )
            await self._store.save_run(result, goal)
            return result
        except Exception as exc:
            result = RunResult(
                run_id=run_id,
                status=RunStatus.FAILED,
                final_output=str(exc),
                artifacts=[],
            )
            await events.emit(
                "run.failed",
                actor="conductor",
                payload={"error_type": type(exc).__name__, "error": str(exc)},
            )
            await self._store.save_run(result, goal)
            raise

    def _build_planner(
        self,
        model_clients: dict[str, ModelClient],
        events: EventEmitter,
        budget: Budget,
    ) -> PlannerAgent:
        name, agent = self._first_agent(AgentKind.PLANNER)
        model_config = self._config.models[agent.model]
        return PlannerAgent(
            name,
            agent,
            model_config.model,
            model_clients[agent.model],
            self._config.limits.max_output_tokens_per_call,
            self._config.limits.max_parse_retries,
            budget.consume_model_call,
            events,
        )

    def _build_specialists(
        self,
        model_clients: dict[str, ModelClient],
        events: EventEmitter,
        budget: Budget,
    ) -> dict[str, SpecialistAgent]:
        specialists: dict[str, SpecialistAgent] = {}
        for name, agent in self._config.agents.items():
            if agent.kind == AgentKind.SPECIALIST:
                model_config = self._config.models[agent.model]
                specialists[name] = SpecialistAgent(
                    name,
                    agent,
                    model_config.model,
                    model_clients[agent.model],
                    self._config.limits.max_output_tokens_per_call,
                    self._config.limits.max_parse_retries,
                    budget.consume_model_call,
                    events,
                )
        return specialists

    def _build_critic(
        self,
        model_clients: dict[str, ModelClient],
        events: EventEmitter,
        budget: Budget,
    ) -> CriticAgent:
        name, agent = self._first_agent(AgentKind.CRITIC)
        model_config = self._config.models[agent.model]
        return CriticAgent(
            name,
            agent,
            model_config.model,
            model_clients[agent.model],
            self._config.limits.max_output_tokens_per_call,
            self._config.limits.max_parse_retries,
            budget.consume_model_call,
            events,
        )

    def _build_finalizer(
        self,
        model_clients: dict[str, ModelClient],
        events: EventEmitter,
        budget: Budget,
    ) -> FinalizerAgent:
        name, agent = self._first_agent(AgentKind.FINALIZER)
        model_config = self._config.models[agent.model]
        return FinalizerAgent(
            name,
            agent,
            model_config.model,
            model_clients[agent.model],
            self._config.limits.max_output_tokens_per_call,
            self._config.limits.max_parse_retries,
            budget.consume_model_call,
            events,
        )

    def _first_agent(self, kind: AgentKind) -> tuple[str, AgentConfig]:
        for name, agent in self._config.agents.items():
            if agent.kind == kind:
                return name, agent
        raise ValueError(f"missing {kind.value} agent")

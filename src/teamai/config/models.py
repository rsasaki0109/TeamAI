from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PositiveInt, model_validator

from teamai.core.budgets import BudgetLimits
from teamai.core.domain import AgentKind, SideEffect

BUILTIN_TOOL_NAMES = frozenset(
    {
        "filesystem.list",
        "filesystem.read",
        "filesystem.write",
    }
)

APPROVAL_TARGETS = BUILTIN_TOOL_NAMES | frozenset(side_effect.value for side_effect in SideEffect)


class TeamSettings(BaseModel):
    name: str = "teamai"


class ProviderCapabilities(BaseModel):
    structured_output: bool = False
    tool_calling: bool = False
    json_mode: bool = True
    max_context_tokens: PositiveInt = 32768


class ModelConfig(BaseModel):
    provider: Literal["fake", "openai_compatible"] = "fake"
    model: str = "fake"
    base_url: str | None = None
    api_key_env: str | None = None
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> ModelConfig:
        if self.provider == "openai_compatible" and self.base_url is None:
            raise ValueError("openai_compatible model requires base_url")
        return self


class AgentConfig(BaseModel):
    kind: AgentKind
    model: str
    capabilities: set[str] = Field(default_factory=set)
    instructions: str = ""
    tools: list[str] = Field(default_factory=list)


class WorkflowConfig(BaseModel):
    strategy: Literal["pipeline", "plan_execute_review"] = "plan_execute_review"


class LimitsConfig(BaseModel):
    max_model_calls: PositiveInt = 30
    max_tool_calls: PositiveInt = 50
    max_tasks: PositiveInt = 8
    max_revisions_per_task: int = Field(default=2, ge=0)
    max_parse_retries: int = Field(default=1, ge=0)
    max_runtime_seconds: PositiveInt = 900
    max_output_tokens_per_call: PositiveInt = 4096
    max_parallel_tasks: PositiveInt = 1

    def to_budget_limits(self) -> BudgetLimits:
        return BudgetLimits(
            max_model_calls=self.max_model_calls,
            max_tool_calls=self.max_tool_calls,
            max_tasks=self.max_tasks,
            max_revisions_per_task=self.max_revisions_per_task,
            max_runtime_seconds=self.max_runtime_seconds,
            max_output_tokens_per_call=self.max_output_tokens_per_call,
            max_parallel_tasks=self.max_parallel_tasks,
        )


class SecurityConfig(BaseModel):
    workspace_root: str = "./workspace"
    require_approval_for: list[str] = Field(default_factory=lambda: ["filesystem.write"])
    require_plan_approval: bool = False
    max_read_bytes: PositiveInt = 262_144
    max_write_bytes: PositiveInt = 262_144

    def resolve_workspace(self, base_dir: Path) -> Path:
        root = Path(self.workspace_root)
        if not root.is_absolute():
            root = base_dir / root
        return root.resolve()


class PersistenceConfig(BaseModel):
    sqlite_path: str = ".teamai/runs.sqlite"

    def resolve_sqlite_path(self, base_dir: Path) -> Path:
        path = Path(self.sqlite_path)
        if not path.is_absolute():
            path = base_dir / path
        return path


class TeamConfig(BaseModel):
    team: TeamSettings = Field(default_factory=TeamSettings)
    models: dict[str, ModelConfig]
    agents: dict[str, AgentConfig]
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)

    @model_validator(mode="after")
    def validate_references(self) -> TeamConfig:
        if not self.models:
            raise ValueError("at least one model must be defined")
        if not self.agents:
            raise ValueError("at least one agent must be defined")
        for agent_name, agent in self.agents.items():
            if agent.model not in self.models:
                raise ValueError(f"agent {agent_name!r} references unknown model {agent.model!r}")
            for tool_name in agent.tools:
                if tool_name not in BUILTIN_TOOL_NAMES:
                    raise ValueError(
                        f"agent {agent_name!r} references unknown tool {tool_name!r}"
                    )
        for approval_target in self.security.require_approval_for:
            if approval_target not in APPROVAL_TARGETS:
                raise ValueError(
                    f"security.require_approval_for references unknown target "
                    f"{approval_target!r}"
                )
        kinds = {agent.kind for agent in self.agents.values()}
        required_kinds = [AgentKind.SPECIALIST, AgentKind.CRITIC, AgentKind.FINALIZER]
        if self.workflow.strategy == "plan_execute_review":
            required_kinds.append(AgentKind.PLANNER)
        for required in required_kinds:
            if required not in kinds:
                raise ValueError(f"team requires at least one {required.value} agent")
        return self

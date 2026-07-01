from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from teamai.core.states import RunStatus, TaskStatus

JsonObject = dict[str, Any]


class AgentKind(StrEnum):
    PLANNER = "planner"
    SPECIALIST = "specialist"
    CRITIC = "critic"
    FINALIZER = "finalizer"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SideEffect(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    EXTERNAL = "external"


class ModelUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: ModelUsage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ModelRequest(BaseModel):
    model: str
    messages: list[ModelMessage]
    output_schema: str | None = None
    max_output_tokens: int
    metadata: JsonObject = Field(default_factory=dict)


class ModelResponse(BaseModel):
    content: str
    usage: ModelUsage = Field(default_factory=ModelUsage)


class AgentDescriptor(BaseModel):
    name: str
    kind: AgentKind
    capabilities: set[str] = Field(default_factory=set)


class Task(BaseModel):
    id: str
    objective: str
    required_capabilities: set[str] = Field(default_factory=set)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]
    expected_artifact_type: str = "text"
    risk: RiskLevel = RiskLevel.LOW
    status: TaskStatus = TaskStatus.PENDING
    revision: int = 0


class PlannedTask(BaseModel):
    id: str
    objective: str
    required_capabilities: set[str] = Field(default_factory=set)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]
    expected_artifact_type: str = "text"
    risk: RiskLevel = RiskLevel.LOW

    def to_task(self) -> Task:
        return Task(
            id=self.id,
            objective=self.objective,
            required_capabilities=set(self.required_capabilities),
            dependencies=list(self.dependencies),
            acceptance_criteria=list(self.acceptance_criteria),
            expected_artifact_type=self.expected_artifact_type,
            risk=self.risk,
        )


class Plan(BaseModel):
    summary: str
    tasks: list[PlannedTask]
    final_acceptance_criteria: list[str]


class ToolCall(BaseModel):
    name: str
    arguments: JsonObject = Field(default_factory=dict)


class ToolObservation(BaseModel):
    name: str
    arguments: JsonObject
    output: JsonObject


class WorkProduct(BaseModel):
    summary: str
    content: str
    produced_files: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    tool_requests: list[ToolCall] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class Review(BaseModel):
    decision: Literal["pass", "revise", "fail"]
    score: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    criteria_results: dict[str, bool] = Field(default_factory=dict)


class FinalOutput(BaseModel):
    final_output: str


class Artifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    task_id: str | None
    type: str
    summary: str
    content: str
    metadata: JsonObject = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject | None = None
    side_effect: SideEffect
    idempotent: bool


class ToolResult(BaseModel):
    output: JsonObject


class ApprovalRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    reason: str
    action: str
    redacted_arguments: JsonObject
    risk: RiskLevel
    preview: str | None = None


class ApprovalDecision(BaseModel):
    approved: bool
    comment: str | None = None


class RunResult(BaseModel):
    run_id: UUID
    status: RunStatus
    final_output: str
    artifacts: list[Artifact]
    usage: ModelUsage = Field(default_factory=ModelUsage)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RunSummary(BaseModel):
    run_id: UUID
    status: RunStatus
    goal: str
    saved_at: str

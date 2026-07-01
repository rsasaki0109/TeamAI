class TeamAIError(Exception):
    """Base exception for TeamAI runtime errors."""


class BudgetExceededError(TeamAIError):
    """Raised when a run exceeds a configured execution limit."""


class PlanValidationError(TeamAIError):
    """Raised when a planner output is invalid for execution."""


class RoutingError(TeamAIError):
    """Raised when no eligible agent can handle a task."""


class ModelOutputError(TeamAIError):
    """Raised when a model response cannot be parsed as the expected schema."""


class ToolExecutionError(TeamAIError):
    """Raised when a tool request cannot be executed safely."""


class ApprovalRejectedError(TeamAIError):
    """Raised when a human or policy approval provider rejects an action."""

from __future__ import annotations

import json
from typing import Any

from teamai.core.domain import ModelRequest, ModelResponse, ModelUsage, RiskLevel


class FakeModelClient:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        schema = request.output_schema
        if schema == "Plan":
            payload = self._plan_payload(request.metadata)
        elif schema == "WorkProduct":
            payload = self._work_product_payload(request.metadata)
        elif schema == "Review":
            payload = self._review_payload(request.metadata)
        elif schema == "FinalOutput":
            payload = self._final_output_payload(request.metadata)
        else:
            payload = {"content": "fake response"}
        content = json.dumps(payload, ensure_ascii=True)
        prompt_chars = sum(len(message.content) for message in request.messages)
        prompt_tokens = max(1, prompt_chars // 4)
        completion_tokens = max(1, len(content) // 4)
        return ModelResponse(
            content=content,
            usage=ModelUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def aclose(self) -> None:
        return None

    def _plan_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        goal = str(metadata.get("goal", "Complete the requested work"))
        agents = metadata.get("available_agents", [])
        required_capabilities: list[str] = []
        if isinstance(agents, list):
            for agent in agents:
                if isinstance(agent, dict) and agent.get("kind") == "specialist":
                    capabilities = agent.get("capabilities", [])
                    if isinstance(capabilities, list):
                        required_capabilities = [str(capability) for capability in capabilities[:1]]
                    break
        risk = RiskLevel.HIGH.value if "high risk" in goal.lower() else RiskLevel.LOW.value
        return {
            "summary": f"Plan for: {goal}",
            "tasks": [
                {
                    "id": "task_1",
                    "objective": goal,
                    "required_capabilities": required_capabilities,
                    "dependencies": [],
                    "acceptance_criteria": ["The requested goal is addressed."],
                    "expected_artifact_type": "text",
                    "risk": risk,
                }
            ],
            "final_acceptance_criteria": ["A final result is produced from reviewed artifacts."],
        }

    def _work_product_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        task = metadata.get("task", {})
        objective = (
            task.get("objective", "Complete the task")
            if isinstance(task, dict)
            else "Complete the task"
        )
        tool_results = metadata.get("tool_results", [])
        if "list workspace" in str(objective).lower() and not tool_results:
            return {
                "summary": "Requested workspace listing",
                "content": "",
                "produced_files": [],
                "evidence": [],
                "tool_requests": [
                    {"name": "filesystem.list", "arguments": {"path": "."}}
                ],
                "confidence": 0.6,
            }
        if "write workspace" in str(objective).lower() and not tool_results:
            return {
                "summary": "Requested workspace write",
                "content": "",
                "produced_files": [],
                "evidence": [],
                "tool_requests": [
                    {
                        "name": "filesystem.write",
                        "arguments": {
                            "path": "teamai-output.txt",
                            "content": "Created by FakeModelClient",
                        },
                    }
                ],
                "confidence": 0.6,
            }
        return {
            "summary": f"Completed: {objective}",
            "content": self._work_product_content(objective, tool_results),
            "produced_files": [],
            "evidence": ["fake-model"],
            "tool_requests": [],
            "confidence": 0.9,
        }

    def _work_product_content(self, objective: object, tool_results: object) -> str:
        if isinstance(tool_results, list) and tool_results:
            return (
                f"FakeModelClient completed the task: {objective}\n"
                f"Tool results: {tool_results}"
            )
        return f"FakeModelClient completed the task: {objective}"

    def _review_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        task = metadata.get("task", {})
        criteria: list[str] = []
        if isinstance(task, dict):
            raw_criteria = task.get("acceptance_criteria", [])
            if isinstance(raw_criteria, list):
                criteria = [str(item) for item in raw_criteria]
        return {
            "decision": "pass",
            "score": 1.0,
            "issues": [],
            "revision_instructions": [],
            "criteria_results": {criterion: True for criterion in criteria},
        }

    def _final_output_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        artifacts = metadata.get("artifacts", [])
        summaries: list[str] = []
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if isinstance(artifact, dict):
                    summaries.append(str(artifact.get("summary", "")))
        joined = "\n".join(f"- {summary}" for summary in summaries if summary)
        return {"final_output": f"Run completed successfully.\n{joined}".strip()}

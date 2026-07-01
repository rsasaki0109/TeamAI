from __future__ import annotations

import asyncio

from teamai.core.domain import ApprovalDecision, ApprovalRequest


class TerminalApprovalProvider:
    async def request(self, request: ApprovalRequest) -> ApprovalDecision:
        prompt = (
            f"\nApproval required: {request.action}\n"
            f"Reason: {request.reason}\n"
            f"Risk: {request.risk.value}\n"
            f"Arguments: {request.redacted_arguments}\n"
        )
        if request.preview:
            prompt += f"Preview:\n{request.preview}\n"
        prompt += "[A]pprove / [R]eject / [C]omment: "
        answer = await asyncio.to_thread(input, prompt)
        normalized = answer.strip().lower()
        if normalized.startswith("a"):
            return ApprovalDecision(approved=True)
        if normalized.startswith("c"):
            comment = await asyncio.to_thread(input, "Comment: ")
            return ApprovalDecision(approved=False, comment=comment)
        return ApprovalDecision(approved=False)

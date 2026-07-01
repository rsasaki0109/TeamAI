from __future__ import annotations

from teamai.core.domain import ApprovalDecision, ApprovalRequest


class AutoApproveProvider:
    async def request(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=True, comment="auto-approved")

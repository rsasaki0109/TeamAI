from __future__ import annotations

from teamai.core.domain import ApprovalDecision, ApprovalRequest


class RejectApprovalProvider:
    async def request(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=False, comment="approval provider was not configured")

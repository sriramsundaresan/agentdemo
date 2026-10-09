from uuid import uuid4


class PolicyService:
    """A decision point only: it never invokes agents or starts workflows."""

    def evaluate(self, intent: str, mode: str = "normal", stage: str = "pre_agent") -> dict:
        financial = intent in {"funds_transfer", "bill_payment"}
        return {
            "decision_id": f"POL-{uuid4().hex[:8]}",
            "decision": "DENY" if mode == "deny_policy" and stage == "pre_agent" else (
                "PERMIT_WITH_OBLIGATIONS" if financial else "PERMIT"
            ),
            "obligations": ["CUSTOMER_CONSENT"] if financial else [],
        }

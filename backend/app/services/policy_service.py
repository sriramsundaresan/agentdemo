from uuid import uuid4


class PolicyService:
    """A decision point only: it never invokes agents or starts workflows."""

    def evaluate(self, intent: str, mode: str = "normal") -> dict:
        return {
            "decision_id": f"POL-{uuid4().hex[:8]}",
            "decision": "DENY" if mode == "deny_policy" else "PERMIT",
            "obligations": ["CUSTOMER_CONSENT"] if intent in {"funds_transfer", "bill_payment"} else [],
        }

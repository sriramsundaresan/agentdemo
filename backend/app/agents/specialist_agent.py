from app.gateways.capability_gateway import capability_gateway


class SpecialistAgent:
    """Scoped preparation only; intentionally has no Commit Gateway dependency."""

    def prepare(self, intent: str, message: str) -> dict:
        if intent == "balance_inquiry":
            return {"balance": capability_gateway.balance("SYN-1001"), "synthetic": True}
        if intent == "funds_transfer":
            import re
            amount = re.search(r"THB\s*([\d,]+(?:\.\d{1,2})?)", message, re.I)
            beneficiary = re.search(r"\bto\s+([A-Za-z]+)", message, re.I)
            return capability_gateway.prepare_transfer(
                (amount.group(1).replace(",", "") if amount else "10000"),
                beneficiary.group(1) if beneficiary else "Somchai",
            )
        if intent == "bill_payment":
            return capability_gateway.prepare_bill_payment()
        return {"answer": "Today's synthetic transfer limit is THB 50,000.", "synthetic": True}


specialist_agent = SpecialistAgent()

from collections import defaultdict


class MockBankAPI:
    def __init__(self):
        self.transactions: dict[str, dict] = {}
        self.next_reference = 1
        self.commit_calls: list[str] = []
        self.reconciliation_calls: list[str] = []

    def commit(self, idempotency_key: str, payload: dict, mode: str) -> dict:
        self.commit_calls.append(idempotency_key)
        if idempotency_key in self.transactions:
            return self.transactions[idempotency_key]
        if mode == "bank_failure":
            result = {"status": "FAILED", "reference": None, "message": "Mock bank declined the request."}
        elif mode in {"unknown_completed", "unknown_failed"}:
            result = {"status": "UNKNOWN", "reference": None, "message": "Checking transaction status"}
            self.transactions[idempotency_key] = result
            return result
        else:
            result = {
                "status": "COMPLETED",
                "reference": f"MOCK-TXN-{self.next_reference:06d}",
                "message": "Synthetic bank transaction completed.",
            }
            self.next_reference += 1
        self.transactions[idempotency_key] = result
        return result

    def status(self, idempotency_key: str, mode: str) -> dict:
        self.reconciliation_calls.append(idempotency_key)
        result = self.transactions.get(idempotency_key, {"status": "UNKNOWN", "reference": None})
        if result["status"] == "UNKNOWN":
            result = {
                "status": "FAILED" if mode == "unknown_failed" else "COMPLETED",
                "reference": None if mode == "unknown_failed" else f"MOCK-TXN-{self.next_reference:06d}",
                "message": "Status reconciled from synthetic mock bank.",
            }
            if result["status"] == "COMPLETED":
                self.next_reference += 1
            self.transactions[idempotency_key] = result
        return result


class CommitGateway:
    def __init__(self, bank: MockBankAPI):
        self.bank = bank

    def commit(self, identity: str, idempotency_key: str, payload: dict, mode: str) -> dict:
        if identity != "transaction-worker":
            raise PermissionError("Commit Gateway accepts only transaction-worker identity")
        return self.bank.commit(idempotency_key, payload, mode)


mock_bank = MockBankAPI()
commit_gateway = CommitGateway(mock_bank)

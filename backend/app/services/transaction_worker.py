import hashlib
import json
from uuid import uuid4

from app.gateways.commit_gateway import commit_gateway, mock_bank


class TransactionWorker:
    """Deterministic commit executor; unknown outcomes are reconciled, never recommitted."""

    def execute(self, item: dict, mode: str, *, dependency_completed: bool = True) -> dict:
        if not item.get("confirmation_record_id"):
            raise PermissionError("A Confirmation Record is required")
        expected = hashlib.sha256(
            json.dumps(item["prepared_payload"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if item.get("payload_hash") != expected:
            raise ValueError("Consent payload hash mismatch")
        if not dependency_completed:
            raise RuntimeError("Work-item dependency has not completed")
        key = item.setdefault("idempotency_key", f"idem-{uuid4().hex}")
        result = commit_gateway.commit("transaction-worker", key, item["prepared_payload"], mode)
        if result["status"] == "UNKNOWN":
            item["status"] = "UNKNOWN"
            reconciled = mock_bank.status(key, mode)
            result = reconciled
        return result


transaction_worker = TransactionWorker()

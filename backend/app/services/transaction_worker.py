import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.gateways.commit_gateway import commit_gateway, mock_bank


class TransactionWorker:
    """Deterministic commit executor; unknown outcomes are reconciled, never recommitted."""

    def execute(self, item: dict, mode: str, *, dependency_completed: bool = True) -> dict:
        if not item.get("confirmation_record_id"):
            raise PermissionError("A Confirmation Record is required")
        if item.get("policy_status") not in {"PERMIT", "PERMIT_WITH_OBLIGATIONS"} or not item.get("policy_decision_id"):
            raise PermissionError("A valid policy decision is required")
        if item.get("transaction_policy_status") not in {"PERMIT", "PERMIT_WITH_OBLIGATIONS"} or not item.get("transaction_policy_decision_id"):
            raise PermissionError("A valid transaction policy decision is required")
        challenge = item.get("challenge")
        if (
            not challenge
            or item.get("confirmation_record_challenge_id") != item.get("confirmation_challenge_id")
            or datetime.fromisoformat(challenge["expires_at"]) <= datetime.now(timezone.utc)
        ):
            raise PermissionError("Confirmation Record is missing or expired")
        if item.get("confirmation_record_payload_hash") != item.get("payload_hash"):
            raise ValueError("Confirmation Record payload hash mismatch")
        expected = hashlib.sha256(
            json.dumps(item["prepared_payload"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if item.get("payload_hash") != expected:
            raise ValueError("Consent payload hash mismatch")
        if not dependency_completed:
            raise RuntimeError("Work-item dependency has not completed")
        key = item.get("idempotency_key") or f"idem-{uuid4().hex}"
        item["idempotency_key"] = key
        result = commit_gateway.commit("transaction-worker", key, item["prepared_payload"], mode)
        if result["status"] == "UNKNOWN":
            item["status"] = "UNKNOWN"
        return result

    def reconcile(self, item: dict, mode: str) -> dict:
        if not item.get("idempotency_key"):
            raise ValueError("A committed idempotency key is required for reconciliation")
        return mock_bank.status(item["idempotency_key"], mode)


transaction_worker = TransactionWorker()

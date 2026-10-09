import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.workflow_access_service import workflow_access_service

EXPIRY_SECONDS = int(os.getenv("CONSENT_EXPIRY_SECONDS", "300"))


class ConfirmationService:
    def create_challenge(self, workflow: dict, item: dict, mode: str):
        payload_hash = hashlib.sha256(
            json.dumps(item["prepared_payload"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(seconds=1 if mode == "expire_consent" else EXPIRY_SECONDS)
        challenge = {
            "challenge_id": f"CH-{uuid4().hex[:10]}",
            "payload_hash": payload_hash,
            "expires_at": expires.isoformat(),
            "work_item_id": item["work_item_id"],
            "workflow_id": workflow["workflow_id"],
            "customer_id": workflow["conversation_id"],
        }
        item["payload_hash"] = payload_hash
        item["confirmation_challenge_id"] = challenge["challenge_id"]
        item["challenge"] = challenge
        return challenge

    def presentation(self, item: dict):
        challenge = item["challenge"]
        return {**item["prepared_payload"], **challenge}

    def decide(self, workflow: dict, item: dict, decision: dict):
        challenge = item.get("challenge")
        if not challenge or decision["challenge_id"] != challenge["challenge_id"]:
            raise ValueError("Invalid confirmation challenge")
        if decision.get("conversation_id") != challenge["customer_id"]:
            raise ValueError("Consent customer does not own this challenge")
        if decision["payload_hash"] != challenge["payload_hash"]:
            raise ValueError("Consent payload hash mismatch")
        if datetime.fromisoformat(challenge["expires_at"]) <= datetime.now(timezone.utc):
            item["status"] = "CONSENT_EXPIRED"
            item["consent_status"] = "EXPIRED"
            return {"acknowledgement": "CONSENT_EXPIRED", "duplicate": False}
        if decision["command_id"] in workflow["processed_command_ids"]:
            return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": True}
        if decision["decision"] == "REJECT":
            item["status"] = "CONSENT_REJECTED"
            item["consent_status"] = "REJECTED"
            workflow["processed_command_ids"].append(decision["command_id"])
            return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": False}
        if not decision.get("evidence"):
            raise ValueError("Mock biometric/PIN evidence is required")
        item["confirmation_record_id"] = f"CONF-{uuid4().hex[:10]}"
        item["confirmation_record_payload_hash"] = challenge["payload_hash"]
        item["confirmation_record_challenge_id"] = challenge["challenge_id"]
        item["consent_status"] = "CONFIRMED"
        item["status"] = "CONFIRMED"
        return workflow_access_service.consent_command(
            workflow,
            {
                "command_id": decision["command_id"],
                "command_type": "WORK_ITEM_CONSENT_APPROVED",
                "work_item_id": item["work_item_id"],
                "challenge_id": challenge["challenge_id"],
                "payload_hash": challenge["payload_hash"],
                "confirmation_record_id": item["confirmation_record_id"],
            },
            "confirmation-service",
        )


confirmation_service = ConfirmationService()

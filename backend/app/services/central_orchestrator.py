import re
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.specialist_agent import specialist_agent
from app.services.confirmation_service import confirmation_service
from app.services.conversation_manager import conversation_manager
from app.services.policy_service import PolicyService
from app.services.workflow_access_service import workflow_access_service


class CentralOrchestrator:
    def __init__(self):
        self.policy = PolicyService()

    def plan(self, message: str) -> list[dict]:
        lower = message.lower()
        items = []
        if "balance" in lower:
            items.append(("balance_inquiry", "read-only", []))
        if "transfer" in lower:
            items.append(("funds_transfer", "financial", []))
        if any(word in lower for word in ("bill", "electricity", "pay")) and "transfer" in lower:
            items.append(("bill_payment", "financial", ["WI-2"]))
        elif any(word in lower for word in ("bill", "electricity")):
            items.append(("bill_payment", "financial", []))
        if not items:
            items.append(("knowledge_question", "knowledge", []))
        return [
            {"work_item_id": f"WI-{index}", "intent": intent, "type": kind, "dependencies": deps}
            for index, (intent, kind, deps) in enumerate(items, 1)
        ]

    async def start_request(self, message: str, conversation_id: str, mode: str, session):
        plan = self.plan(message)
        workflow_id = f"WF-{uuid4().hex[:12]}"
        items = []
        for candidate in plan:
            decision = self.policy.evaluate(candidate["intent"], mode)
            now = datetime.now(timezone.utc).isoformat()
            item = {
                **candidate, "status": "POLICY_CHECK", "agent_id": "specialist-agent",
                "policy_status": decision["decision"], "policy_decision_id": decision["decision_id"],
                "consent_status": "NOT_REQUIRED", "transaction_status": "NOT_STARTED",
                "last_update": now, "validation_reference": None, "result": None,
                "confirmation_record_id": None, "bank_reference": None, "idempotency_key": None,
            }
            if decision["decision"] == "DENY":
                item["status"] = "FAILED"
                item["error_code"] = "POLICY_DENIED"
            elif candidate["dependencies"]:
                item["status"] = "BLOCKED_BY_DEPENDENCY"
                item["consent_status"] = "PENDING"
            else:
                item["status"] = "PREPARING"
                item["prepared_payload"] = specialist_agent.prepare(candidate["intent"], message)
                item["validation_reference"] = f"VAL-{uuid4().hex[:8]}"
                if candidate["type"] == "financial":
                    item["status"] = "VALIDATING"
                    item["consent_status"] = "REQUIRED"
                    confirmation_service.create_challenge(
                        {"workflow_id": workflow_id, "conversation_id": conversation_id}, item, mode
                    )
                    item["status"] = "AWAITING_CONSENT"
                else:
                    item["status"] = "COMPLETED"
                    item["transaction_status"] = "NOT_APPLICABLE"
                    item["result"] = (
                        f"Synthetic balance: THB {item['prepared_payload']['balance']['balance']}"
                        if candidate["intent"] == "balance_inquiry"
                        else item["prepared_payload"].get("answer")
                    )
            items.append(item)
        workflow = {
            "workflow_id": workflow_id, "conversation_id": conversation_id,
            "request_status": "IN_PROGRESS", "work_items": items,
            "processed_command_ids": [], "created_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": f"CORR-{uuid4().hex[:10]}", "original_message": message,
            "mode": mode,
        }
        workflow_access_service.start(workflow, "central-orchestrator")
        record = session.add_workflow(workflow)
        await conversation_manager.emit(workflow_id, "request.workflow.started", "WORKFLOW_STARTED", mode=mode)
        for item in items:
            event_name = "workitem.awaiting_consent" if item["status"] == "AWAITING_CONSENT" else (
                "workitem.blocked" if item["status"] == "BLOCKED_BY_DEPENDENCY" else "workitem.completed"
            )
            await conversation_manager.emit(
                workflow_id, event_name, item["status"], work_item_id=item["work_item_id"], mode=mode
            )
        return record


central_orchestrator = CentralOrchestrator()

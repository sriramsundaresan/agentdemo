import asyncio
import re
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.specialist_agent import specialist_agent
from app.services.confirmation_service import confirmation_service
from app.services.conversation_manager import conversation_manager
from app.services.policy_service import PolicyService
from app.services.workflow_access_service import workflow_access_service
from app.workflow.request_workflow import RequestWorkflow


class CentralOrchestrator:
    def __init__(self):
        self.policy = PolicyService()

    def plan(self, message: str) -> list[dict]:
        lower = message.lower()
        items = []
        if "balance" in lower:
            items.append(("balance_inquiry", "read-only", []))
        transfer_action = re.search(r"\btransfer\s+(?:thb|money|funds|from)\b|\btransfer\s+.{1,60}\s+to\b", lower)
        if transfer_action:
            items.append(("funds_transfer", "financial", []))
        if any(word in lower for word in ("bill", "electricity", "pay")) and transfer_action:
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
            items.append(item)

        preparable = [item for item in items if item["status"] == "PREPARING"]
        prepared = await asyncio.gather(*[
            asyncio.to_thread(specialist_agent.prepare, item["intent"], message)
            for item in preparable
        ])
        for item, payload in zip(preparable, prepared):
            item["prepared_payload"] = payload
            item["validation_reference"] = f"VAL-{uuid4().hex[:8]}"
            if item["type"] == "financial":
                item["status"] = "VALIDATING"
                transaction_policy = self.policy.evaluate(
                    item["intent"], mode, stage="transaction"
                )
                item["transaction_policy_status"] = transaction_policy["decision"]
                item["transaction_policy_decision_id"] = transaction_policy["decision_id"]
                if transaction_policy["decision"] == "DENY":
                    item["status"] = "FAILED"
                    item["error_code"] = "TRANSACTION_POLICY_DENIED"
                    continue
                item["consent_status"] = "REQUIRED"
                confirmation_service.create_challenge(
                    {"workflow_id": workflow_id, "conversation_id": conversation_id}, item, mode
                )
                item["status"] = "AWAITING_CONSENT"
            else:
                item["status"] = "COMPLETED"
                item["transaction_status"] = "NOT_APPLICABLE"
                item["result"] = (
                    f"Synthetic balance: THB {payload['balance']['balance']}"
                    if item["intent"] == "balance_inquiry"
                    else payload.get("answer")
                )

        terminal = {"COMPLETED", "FAILED", "CONSENT_REJECTED", "CONSENT_EXPIRED"}
        request_status = "IN_PROGRESS"
        if all(item["status"] in terminal for item in items):
            request_status = "COMPLETED" if all(item["status"] == "COMPLETED" for item in items) else "PARTIAL_FAILURE"
        workflow = RequestWorkflow.from_dict({
            "workflow_id": workflow_id, "conversation_id": conversation_id,
            "request_status": request_status, "work_items": items,
            "processed_command_ids": [], "created_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": f"CORR-{uuid4().hex[:10]}", "original_message": message,
            "mode": mode,
        }).to_dict()
        workflow_access_service.start(workflow, "central-orchestrator")
        record = session.add_workflow(workflow)
        await conversation_manager.emit(
            workflow_id, "request.workflow.started", "WORKFLOW_STARTED",
            mode=mode, conversation_id=conversation_id,
        )
        for item in items:
            await conversation_manager.emit(
                workflow_id, "workitem.received", "RECEIVED",
                work_item_id=item["work_item_id"], mode=mode,
                conversation_id=conversation_id,
            )
            await conversation_manager.emit(
                workflow_id, "workitem.policy_checked", "POLICY_CHECK",
                work_item_id=item["work_item_id"], caller="Central Orchestrator",
                executor="Policy Service", mode=mode, conversation_id=conversation_id,
            )
            if item["status"] == "PREPARING" or item.get("prepared_payload"):
                await conversation_manager.emit(
                    workflow_id, "workitem.preparing", "PREPARING",
                    work_item_id=item["work_item_id"], caller="Request Workflow",
                    executor="Specialist Agent", mode=mode, conversation_id=conversation_id,
                )
                await conversation_manager.emit(
                    workflow_id, "workitem.validating", "VALIDATING",
                    work_item_id=item["work_item_id"], caller="Specialist Agent",
                    executor="Read/Prepare Capability Gateway", mode=mode,
                    conversation_id=conversation_id,
                )
                if item["type"] == "financial":
                    await conversation_manager.emit(
                        workflow_id, "workitem.transaction_policy_checked", "POLICY_CHECK",
                        work_item_id=item["work_item_id"], caller="Request Workflow",
                        executor="Policy Service", mode=mode,
                        conversation_id=conversation_id,
                    )
            event_name = {
                "AWAITING_CONSENT": "workitem.awaiting_consent",
                "BLOCKED_BY_DEPENDENCY": "workitem.blocked",
                "FAILED": "workitem.failed",
                "COMPLETED": "workitem.completed",
            }.get(item["status"], "workitem.preparing")
            await conversation_manager.emit(
                workflow_id, event_name, item["status"], work_item_id=item["work_item_id"],
                mode=mode, conversation_id=conversation_id,
            )
        if request_status == "COMPLETED":
            await conversation_manager.emit(
                workflow_id, "request.workflow.completed", "COMPLETED",
                mode=mode, conversation_id=conversation_id,
            )
        elif request_status == "PARTIAL_FAILURE":
            await conversation_manager.emit(
                workflow_id, "request.workflow.partial_failure", "PARTIAL_FAILURE",
                mode=mode, conversation_id=conversation_id,
            )
        return record


central_orchestrator = CentralOrchestrator()

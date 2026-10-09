import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from app.agents.specialist_agent import specialist_agent
from app.contracts.schemas import ConsentDecision, DeveloperControls, MessageRequest, WorkflowCommand, WorkflowStartRequest
from app.events.bus import event_bus
from app.gateways.capability_gateway import capability_gateway
from app.persistence.database import Base, SessionLocal, engine
from app.persistence.models import WorkflowRecord
from app.services.central_orchestrator import central_orchestrator
from app.services.confirmation_service import confirmation_service
from app.services.conversation_manager import conversation_manager
from app.services.transaction_worker import transaction_worker
from app.workflow.repository import WorkflowRepository

mode = "normal"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Synthetic Conversational Banking Mock",
    description="Local mock API. Every account, balance, customer and transaction is synthetic.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_body(code: str, category: str, retryability: str, customer_action: str | None = None):
    return {
        "schemaVersion": "1.0", "errorId": f"ERR-{uuid4().hex[:10]}",
        "code": code, "category": category, "retryability": retryability,
        "customerAction": customer_action, "correlationId": f"CORR-{uuid4().hex[:10]}",
    }


@app.exception_handler(HTTPException)
async def api_http_error(_: Request, error: HTTPException):
    category = {403: "AUTHORIZATION", 404: "NOT_FOUND", 409: "BUSINESS_VALIDATION", 422: "BUSINESS_VALIDATION"}.get(
        error.status_code, "REQUEST_ERROR"
    )
    detail = str(error.detail)
    code = detail.upper().replace(" ", "_") if detail.isascii() and detail.isalpha() else {
        403: "FORBIDDEN", 404: "NOT_FOUND", 409: "BUSINESS_VALIDATION", 422: "INVALID_REQUEST",
    }.get(error.status_code, "REQUEST_ERROR")
    retryability = "NOT_RETRYABLE" if error.status_code < 500 else "RETRYABLE"
    action = "RESTART_CONFIRMATION" if "EXPIRED" in code else None
    return JSONResponse(
        status_code=error.status_code,
        content={**_error_body(code, category, retryability, action), "message": detail},
    )


@app.exception_handler(RequestValidationError)
async def api_validation_error(_: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            **_error_body("INVALID_REQUEST", "BUSINESS_VALIDATION", "NOT_RETRYABLE"),
            "message": str(error.errors()),
        },
    )


def _repository():
    return SessionLocal()


def _record(session, workflow_id: str):
    record = WorkflowRepository(session).get(workflow_id)
    if not record:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return record


def _item(workflow: dict, work_item_id: str):
    item = next((entry for entry in workflow["work_items"] if entry["work_item_id"] == work_item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item


async def _event(workflow: dict, name: str, status: str, item: dict | None = None,
                 caller: str = "Request Workflow", executor: str = "Conversation Manager",
                 message: str | None = None):
    return await conversation_manager.emit(
        workflow["workflow_id"], name, status,
        work_item_id=item["work_item_id"] if item else None,
        caller=caller, executor=executor, mode=workflow.get("mode", mode),
        conversation_id=workflow["conversation_id"],
        message=message,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "synthetic_data": True}


@app.post("/api/conversations/{conversation_id}/messages")
async def submit_message(conversation_id: str, body: MessageRequest):
    session = _repository()
    try:
        actual_conversation = body.conversation_id or conversation_id
        record = await central_orchestrator.start_request(body.message, actual_conversation, mode, WorkflowRepository(session))
        return {
            "schemaVersion": "1.0", "messageId": str(uuid4()),
            "conversationId": record.conversation_id, "workflowId": record.id,
            "correlationId": record.data["correlation_id"], "traceId": str(uuid4()),
            "occurredAt": datetime.now(timezone.utc).isoformat(),
            "requestStatus": "WORKFLOW_STARTED", "workflow": record.data,
        }
    finally:
        session.close()


@app.get("/api/workflows")
def list_workflows(x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity not in {"conversation-manager", "workflow-access-service"}:
        raise HTTPException(status_code=403, detail="Internal service identity required")
    session = _repository()
    try:
        records = session.scalars(select(WorkflowRecord).order_by(WorkflowRecord.updated_at.desc())).all()
        return {"workflows": [record.data for record in records], "synthetic": True}
    finally:
        session.close()


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "conversation-manager":
        raise HTTPException(status_code=403, detail="Conversation Manager identity required")
    session = _repository()
    try:
        record = _record(session, workflow_id)
        conversation_manager.rebuild_projection(record.data)
        return record.data
    finally:
        session.close()


@app.get("/api/workflows/{workflow_id}/customer-visible-state")
def customer_visible_state(workflow_id: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity not in {"conversation-manager", "confirmation-service"}:
        raise HTTPException(status_code=403, detail="Internal service identity required")
    session = _repository()
    try:
        record = _record(session, workflow_id)
        conversation_manager.rebuild_projection(record.data)
        return {"workflow": record.data, "projection": conversation_manager.projections.get(workflow_id, {})}
    finally:
        session.close()


@app.post("/api/workflows")
def internal_start_workflow(payload: WorkflowStartRequest, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "central-orchestrator":
        raise HTTPException(status_code=403, detail="Central Orchestrator identity required")
    session = _repository()
    try:
        record = WorkflowRepository(session).add_workflow(payload.workflow)
        return {"workflow_id": record.id, "acknowledgement": "WORKFLOW_STARTED"}
    finally:
        session.close()


@app.post("/api/workflows/{workflow_id}/commands")
def workflow_command(workflow_id: str, command: WorkflowCommand, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "confirmation-service":
        raise HTTPException(status_code=403, detail="Confirmation Service identity required")
    session = _repository()
    try:
        record = _record(session, workflow_id)
        command = command.model_dump()
        if command["command_type"] != "WORK_ITEM_CONSENT_APPROVED":
            raise HTTPException(status_code=422, detail="Unsupported workflow command")
        item = _item(record.data, command["work_item_id"])
        if (
            item.get("confirmation_challenge_id") != command["challenge_id"]
            or item.get("confirmation_record_id") != command["confirmation_record_id"]
            or item.get("confirmation_record_payload_hash") != command["payload_hash"]
        ):
            raise HTTPException(status_code=409, detail="Consent command does not match the validated work item")
        command_id = command["command_id"]
        if command_id in record.data["processed_command_ids"]:
            return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": True}
        record.data["processed_command_ids"].append(command_id)
        WorkflowRepository(session).save(record)
        return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": False}
    finally:
        session.close()


@app.post("/api/workflows/{workflow_id}/cancel")
def cancel_workflow(workflow_id: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity not in {"conversation-manager", "central-orchestrator"}:
        raise HTTPException(status_code=403, detail="Internal service identity required")
    session = _repository()
    try:
        record = _record(session, workflow_id)
        record.data["request_status"] = "CANCELLED"
        WorkflowRepository(session).save(record)
        return record.data
    finally:
        session.close()


@app.get("/api/workflows/{workflow_id}/events")
async def workflow_events(workflow_id: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "conversation-manager":
        raise HTTPException(status_code=403, detail="Conversation Manager identity required")
    session = _repository()
    try:
        _record(session, workflow_id)
    finally:
        session.close()
    queue = event_bus.subscribe(workflow_id)

    async def stream():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"id: {event['event_id']}\nevent: workflow\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(workflow_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/workflows/{workflow_id}/trace")
def workflow_trace(workflow_id: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "conversation-manager":
        raise HTTPException(status_code=403, detail="Conversation Manager identity required")
    session = _repository()
    try:
        _record(session, workflow_id)
        return {"entries": [e for e in event_bus.history if e["workflow_id"] == workflow_id]}
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}/workflows/{workflow_id}")
def conversation_workflow_state(conversation_id: str, workflow_id: str):
    session = _repository()
    try:
        record = _record(session, workflow_id)
        if record.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Workflow not found")
        conversation_manager.rebuild_projection(record.data)
        return record.data
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}/workflows")
def conversation_workflows(conversation_id: str):
    session = _repository()
    try:
        records = session.scalars(
            select(WorkflowRecord)
            .where(WorkflowRecord.conversation_id == conversation_id)
            .order_by(WorkflowRecord.updated_at.desc())
        ).all()
        for record in records:
            conversation_manager.rebuild_projection(record.data)
        return {"workflows": [record.data for record in records]}
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}/workflows/{workflow_id}/trace")
def conversation_workflow_trace(conversation_id: str, workflow_id: str):
    session = _repository()
    try:
        record = _record(session, workflow_id)
        if record.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return {"entries": [e for e in event_bus.history if e["workflow_id"] == workflow_id]}
    finally:
        session.close()


@app.get("/api/conversations/{conversation_id}/workflows/{workflow_id}/events")
async def conversation_workflow_events(conversation_id: str, workflow_id: str):
    session = _repository()
    try:
        record = _record(session, workflow_id)
        if record.conversation_id != conversation_id:
            raise HTTPException(status_code=404, detail="Workflow not found")
    finally:
        session.close()
    queue = event_bus.subscribe(workflow_id)

    async def stream():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"id: {event['event_id']}\nevent: workflow\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(workflow_id, queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/capabilities/accounts/eligible")
def eligible_accounts(x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "specialist-agent":
        raise HTTPException(status_code=403, detail="Specialist Agent identity required")
    return {"accounts": capability_gateway.eligible_accounts(), "synthetic": True}


@app.get("/api/capabilities/accounts/{account_ref}/balance")
def balance(account_ref: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "specialist-agent":
        raise HTTPException(status_code=403, detail="Specialist Agent identity required")
    try:
        return capability_gateway.balance(account_ref)
    except KeyError:
        raise HTTPException(status_code=404, detail="Synthetic account not found")


@app.post("/api/capabilities/transfers/prepare")
def prepare_transfer(payload: dict, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "specialist-agent":
        raise HTTPException(status_code=403, detail="Specialist Agent identity required")
    return capability_gateway.prepare_transfer(str(payload.get("amount", "10000")), str(payload.get("beneficiary", "Somchai")))


@app.post("/api/capabilities/bill-payments/prepare")
def prepare_bill_payment(x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "specialist-agent":
        raise HTTPException(status_code=403, detail="Specialist Agent identity required")
    return capability_gateway.prepare_bill_payment()


@app.post("/api/confirmation-challenges")
def create_confirmation_challenge(payload: dict, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity not in {"request-workflow", "central-orchestrator"}:
        raise HTTPException(status_code=403, detail="Workflow identity required")
    session = _repository()
    try:
        record = _record(session, payload.get("workflow_id", ""))
        item = _item(record.data, payload.get("work_item_id", ""))
        if item["type"] != "financial" or not item.get("prepared_payload"):
            raise HTTPException(status_code=422, detail="Financial prepared item required")
        challenge = confirmation_service.create_challenge(record.data, item, mode)
        WorkflowRepository(session).save(record)
        return challenge
    finally:
        session.close()


@app.get("/api/confirmation-challenges/{challenge_id}/presentation")
def challenge_presentation(challenge_id: str):
    session = _repository()
    try:
        records = session.scalars(select(WorkflowRecord)).all()
        for record in records:
            for item in record.data["work_items"]:
                if item.get("confirmation_challenge_id") == challenge_id:
                    return confirmation_service.presentation(item)
        raise HTTPException(status_code=404, detail="Challenge not found")
    finally:
        session.close()


@app.post("/api/confirmation-challenges/{challenge_id}/decision")
async def consent_decision(challenge_id: str, body: ConsentDecision):
    session = _repository()
    try:
        records = session.scalars(select(WorkflowRecord)).all()
        record = None
        item = None
        for candidate in records:
            match = next((i for i in candidate.data["work_items"] if i.get("confirmation_challenge_id") == challenge_id), None)
            if match:
                record, item = candidate, match
                break
        if record is None or item is None:
            raise HTTPException(status_code=404, detail="Challenge not found")
        if body.challenge_id != challenge_id:
            raise HTTPException(status_code=422, detail="Challenge ID mismatch")
        decision = body.model_dump()
        if mode == "reject_consent":
            decision["decision"] = "REJECT"
        try:
            ack = confirmation_service.decide(record.data, item, decision)
        except (ValueError, PermissionError) as error:
            raise HTTPException(status_code=409, detail=str(error))
        if ack["acknowledgement"] == "CONSENT_EXPIRED":
            await _event(record.data, "workitem.failed", "CONSENT_EXPIRED", item)
        elif decision["decision"] == "REJECT":
            await _event(record.data, "workitem.failed", "CONSENT_REJECTED", item)
        elif not ack.get("duplicate"):
            await _event(record.data, "workitem.consent_received", "CONSENT_RECEIVED", item,
                         caller="Confirmation Service", executor="Workflow Access Service")
            await _execute_and_advance(record.data, item, session)
        WorkflowRepository(session).save(record)
        return {**ack, "workflowId": record.id, "workItemId": item["work_item_id"]}
    finally:
        session.close()


async def _execute_and_advance(workflow: dict, item: dict, session):
    item["status"] = "EXECUTING"
    item["transaction_status"] = "EXECUTING"
    item["last_update"] = datetime.now(timezone.utc).isoformat()
    await _event(workflow, "workitem.executing", "EXECUTING", item,
                 caller="Request Workflow", executor="Transaction Worker")
    was_unknown = False
    try:
        completed_dependencies = all(
            next((candidate for candidate in workflow["work_items"] if candidate["work_item_id"] == dependency), {}).get("status") == "COMPLETED"
            for dependency in item.get("dependencies", [])
        )
        result = transaction_worker.execute(
            item, workflow.get("mode", "normal"), dependency_completed=completed_dependencies
        )
    except (PermissionError, ValueError, RuntimeError) as error:
        item["status"] = "FAILED"
        item["error_code"] = str(error)
        await _event(workflow, "workitem.failed", "FAILED", item)
        return
    if result["status"] == "UNKNOWN":
        was_unknown = True
        item["status"] = "UNKNOWN"
        item["transaction_status"] = "UNKNOWN"
        item["last_update"] = datetime.now(timezone.utc).isoformat()
        record = WorkflowRepository(session).get(workflow["workflow_id"])
        if record:
            WorkflowRepository(session).save(record)
        await _event(workflow, "workitem.unknown", "UNKNOWN", item, message="Checking transaction status")
        result = await asyncio.to_thread(
            transaction_worker.reconcile, item, workflow.get("mode", "normal")
        )
    item["transaction_status"] = result["status"]
    item["last_update"] = datetime.now(timezone.utc).isoformat()
    if result["status"] == "COMPLETED":
        item["status"] = "COMPLETED"
        item["bank_reference"] = result.get("reference")
        item["result"] = f"Synthetic bank reference {item['bank_reference']}"
        await _event(workflow, "workitem.completed", "COMPLETED", item,
                     caller="Status Reconciliation" if was_unknown else "Transaction Worker",
                     executor="Mock Bank API")
        for dependent in workflow["work_items"]:
            if item["work_item_id"] in dependent.get("dependencies", []) and dependent["status"] == "BLOCKED_BY_DEPENDENCY":
                dependent["status"] = "PREPARING"
                await _event(workflow, "workitem.preparing", "PREPARING", dependent,
                             caller="Request Workflow", executor="Specialist Agent")
                dependent["prepared_payload"] = await asyncio.to_thread(
                    specialist_agent.prepare, dependent["intent"], workflow["original_message"]
                )
                dependent["status"] = "VALIDATING"
                dependent["last_update"] = datetime.now(timezone.utc).isoformat()
                dependent["validation_reference"] = f"VAL-{uuid4().hex[:8]}"
                transaction_policy = central_orchestrator.policy.evaluate(
                    dependent["intent"], workflow.get("mode", "normal"), stage="transaction"
                )
                dependent["transaction_policy_status"] = transaction_policy["decision"]
                dependent["transaction_policy_decision_id"] = transaction_policy["decision_id"]
                await _event(workflow, "workitem.validating", "VALIDATING", dependent,
                             caller="Specialist Agent", executor="Read/Prepare Capability Gateway")
                await _event(workflow, "workitem.transaction_policy_checked", "POLICY_CHECK", dependent,
                             caller="Request Workflow", executor="Policy Service")
                if transaction_policy["decision"] == "DENY":
                    dependent["status"] = "FAILED"
                    dependent["error_code"] = "TRANSACTION_POLICY_DENIED"
                    await _event(workflow, "workitem.failed", "FAILED", dependent)
                    continue
                confirmation_service.create_challenge(workflow, dependent, workflow.get("mode", "normal"))
                dependent["status"] = "AWAITING_CONSENT"
                dependent["consent_status"] = "REQUIRED"
                await _event(workflow, "workitem.awaiting_consent", "AWAITING_CONSENT", dependent)
    elif result["status"] == "FAILED":
        item["status"] = "FAILED"
        item["error_code"] = result.get("message", "BANK_FAILURE")
        await _event(workflow, "workitem.failed", "FAILED", item, caller="Transaction Worker", executor="Mock Bank API")
    else:
        item["status"] = "FAILED"
        item["error_code"] = "RECONCILED_FAILURE" if was_unknown else result.get("message", "BANK_FAILURE")
        await _event(workflow, "workitem.failed", "FAILED", item,
                     caller="Status Reconciliation" if was_unknown else "Transaction Worker",
                     executor="Mock Bank API")
    if all(i["status"] in {"COMPLETED", "FAILED", "CONSENT_REJECTED", "CONSENT_EXPIRED"} for i in workflow["work_items"]):
        workflow["request_status"] = "COMPLETED" if all(i["status"] == "COMPLETED" for i in workflow["work_items"]) else "PARTIAL_FAILURE"
        event_name = "request.workflow.completed" if workflow["request_status"] == "COMPLETED" else "request.workflow.partial_failure"
        await _event(workflow, event_name, workflow["request_status"])


@app.post("/api/developer/controls")
def set_developer_controls(body: DeveloperControls):
    global mode
    mode = body.mode
    return {"mode": mode, "synthetic": True}


@app.get("/api/developer/controls")
def get_developer_controls():
    return {"mode": mode}


@app.post("/api/commit/transfers")
def guarded_commit(payload: dict, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "transaction-worker":
        raise HTTPException(status_code=403, detail="Commit is restricted to transaction-worker")
    return {"accepted": True, "identity": x_mock_service_identity}


@app.post("/api/commit/bill-payments")
def guarded_bill_commit(payload: dict, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "transaction-worker":
        raise HTTPException(status_code=403, detail="Commit is restricted to transaction-worker")
    return {"accepted": True, "identity": x_mock_service_identity}


@app.get("/api/bank/transactions/{idempotency_key}/status")
def bank_status(idempotency_key: str, x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "transaction-worker":
        raise HTTPException(status_code=403, detail="Transaction Worker identity required")
    from app.gateways.commit_gateway import mock_bank
    return mock_bank.status(idempotency_key, mode)


@app.get("/api/technical-trace")
def technical_trace(x_mock_service_identity: str = Header(default="")):
    if x_mock_service_identity != "conversation-manager":
        raise HTTPException(status_code=403, detail="Conversation Manager identity required")
    return {"entries": event_bus.history}

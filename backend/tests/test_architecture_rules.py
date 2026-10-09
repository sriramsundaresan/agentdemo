import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.agents.specialist_agent import specialist_agent
from app.events.bus import EventBus
from app.persistence.database import Base
from app.main import app
from app.gateways.commit_gateway import mock_bank
from app.services.central_orchestrator import central_orchestrator
from app.services.confirmation_service import confirmation_service
from app.services.conversation_manager import ConversationManager
from app.services.policy_service import PolicyService
from app.services.transaction_worker import transaction_worker
from app.workflow.repository import WorkflowRepository


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def consent_workflow(item_status="AWAITING_CONSENT", expires_in=60):
    payload = {"amount": "10000.00", "currency": "THB"}
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    item = {
        "work_item_id": "WI-1", "intent": "funds_transfer", "type": "financial",
        "status": item_status, "prepared_payload": payload, "payload_hash": payload_hash,
        "confirmation_challenge_id": "CH-1", "confirmation_record_id": None,
        "confirmation_record_payload_hash": None, "confirmation_record_challenge_id": None,
        "policy_status": "PERMIT_WITH_OBLIGATIONS",
        "policy_decision_id": "POL-1", "transaction_policy_status": "PERMIT_WITH_OBLIGATIONS",
        "transaction_policy_decision_id": "POL-TXN-1",
        "consent_status": "REQUIRED", "dependencies": [],
        "challenge": {
            "challenge_id": "CH-1", "payload_hash": payload_hash,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
            "customer_id": "CONV-1",
        },
    }
    return {
        "workflow_id": "WF-1", "conversation_id": "CONV-1", "processed_command_ids": [],
        "work_items": [item], "mode": "normal",
    }, item


def test_one_request_creates_one_workflow_with_n_work_items(db_session):
    async def create():
        return await central_orchestrator.start_request(
            "Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.",
            "CONV-1", "normal", WorkflowRepository(db_session),
        )

    record = asyncio.run(create())
    assert record.id.startswith("WF-")
    assert len(record.data["work_items"]) == 3
    assert record.data["work_items"][2]["dependencies"] == ["WI-2"]
    assert record.data["work_items"][2]["status"] == "BLOCKED_BY_DEPENDENCY"
    assert db_session.query(type(record)).count() == 1


def test_policy_service_only_returns_a_decision():
    policy = PolicyService()
    assert policy.evaluate("funds_transfer")["decision"] == "PERMIT_WITH_OBLIGATIONS"
    assert not hasattr(policy, "start_workflow")
    assert not hasattr(policy, "invoke_agent")


def test_transfer_limit_question_is_knowledge_not_a_financial_work_item():
    plan = central_orchestrator.plan("What is today's transfer limit?")
    assert len(plan) == 1
    assert plan[0]["intent"] == "knowledge_question"


def test_browser_cannot_call_internal_workflow_or_capability_apis():
    client = TestClient(app)
    workflow_response = client.get("/api/workflows/WF-internal")
    capability_response = client.get("/api/capabilities/accounts/eligible")
    assert workflow_response.status_code == 403
    assert workflow_response.json()["code"] == "FORBIDDEN"
    assert capability_response.status_code == 403


def test_unknown_bank_outcome_is_visible_and_reconciled_without_retry():
    conversation_id = f"CONV-{uuid4().hex[:8]}"
    with TestClient(app) as client:
        try:
            client.post("/api/developer/controls", json={"mode": "unknown_completed"})
            started = client.post(
                f"/api/conversations/{conversation_id}/messages",
                json={"message": "Transfer THB 1,234 to Somchai."},
            )
            assert started.status_code == 200
            workflow = started.json()["workflow"]
            item = workflow["work_items"][0]
            commits_before = len(mock_bank.commit_calls)
            approved = client.post(
                f"/api/confirmation-challenges/{item['confirmation_challenge_id']}/decision",
                json={
                    "challenge_id": item["confirmation_challenge_id"],
                    "conversation_id": conversation_id,
                    "payload_hash": item["payload_hash"],
                    "decision": "APPROVE",
                    "evidence_method": "MOCK_BIOMETRIC",
                    "evidence": "synthetic-demo-evidence",
                    "command_id": f"CMD-{uuid4().hex}",
                },
            )
            assert approved.status_code == 200
            latest = client.get(
                f"/api/conversations/{conversation_id}/workflows/{workflow['workflow_id']}"
            ).json()
            events = client.get(
                f"/api/conversations/{conversation_id}/workflows/{workflow['workflow_id']}/trace"
            ).json()["entries"]
            assert latest["work_items"][0]["status"] == "COMPLETED"
            assert any(event["response_status"] == "UNKNOWN" for event in events)
            assert any(event["caller"] == "Status Reconciliation" for event in events)
            assert len(mock_bank.commit_calls) == commits_before + 1
        finally:
            client.post("/api/developer/controls", json={"mode": "normal"})


def test_specialist_agent_has_no_commit_gateway_access():
    from app.gateways.commit_gateway import commit_gateway

    assert not hasattr(specialist_agent, "commit")
    assert not hasattr(specialist_agent, "commit_gateway")
    assert "commit_gateway" not in specialist_agent.prepare.__code__.co_names
    with pytest.raises(PermissionError):
        commit_gateway.commit("specialist-agent", "agent-key", {}, "normal")


def test_financial_execution_requires_confirmation_record():
    _, item = consent_workflow()
    with pytest.raises(PermissionError, match="Confirmation Record"):
        transaction_worker.execute(item, "normal")


def test_payload_hash_mismatch_blocks_execution():
    _, item = consent_workflow()
    item["confirmation_record_id"] = "CONF-1"
    item["confirmation_record_payload_hash"] = item["payload_hash"]
    item["confirmation_record_challenge_id"] = "CH-1"
    item["payload_hash"] = "wrong-hash"
    with pytest.raises(ValueError, match="payload hash"):
        transaction_worker.execute(item, "normal")


def test_duplicate_consent_command_is_idempotent():
    workflow, item = consent_workflow()
    request = {
        "challenge_id": "CH-1", "conversation_id": "CONV-1", "payload_hash": item["payload_hash"],
        "decision": "APPROVE", "evidence": "mock", "command_id": "CMD-1",
    }
    with pytest.raises(ValueError, match="customer"):
        confirmation_service.decide(workflow, item, {**request, "conversation_id": "OTHER-CUSTOMER"})
    first = confirmation_service.decide(workflow, item, request)
    second = confirmation_service.decide(workflow, item, request)
    assert first["acknowledgement"] == "CONSENT_RECEIVED"
    assert second["duplicate"] is True
    assert workflow["processed_command_ids"].count("CMD-1") == 1


def test_duplicate_workflow_event_does_not_duplicate_projection_message():
    async def exercise():
        manager = ConversationManager()
        bus = EventBus()
        bus.subscribe_handler(manager.project_event)
        event = {
            "event_id": "EV-1", "workflow_id": "WF-1", "event_name": "workitem.completed",
            "response_status": "COMPLETED", "occurred_at": "now",
        }
        await bus.publish(event, duplicate=True)
        return manager.projections["WF-1"]

    projection = asyncio.run(exercise())
    assert len(projection["messages"]) == 1


def test_dependent_work_item_cannot_execute_before_dependency():
    _, item = consent_workflow()
    item["confirmation_record_id"] = "CONF-1"
    item["confirmation_record_payload_hash"] = item["payload_hash"]
    item["confirmation_record_challenge_id"] = "CH-1"
    with pytest.raises(RuntimeError, match="dependency"):
        transaction_worker.execute(item, "normal", dependency_completed=False)


def test_consent_rejection_prevents_execution():
    workflow, item = consent_workflow()
    response = confirmation_service.decide(workflow, item, {
        "challenge_id": "CH-1", "conversation_id": "CONV-1", "payload_hash": item["payload_hash"],
        "decision": "REJECT", "evidence": "mock", "command_id": "CMD-REJECT",
    })
    assert response["acknowledgement"] == "CONSENT_RECEIVED"
    assert item["status"] == "CONSENT_REJECTED"
    with pytest.raises(PermissionError):
        transaction_worker.execute(item, "normal")


def test_expired_consent_prevents_execution():
    workflow, item = consent_workflow(expires_in=-1)
    response = confirmation_service.decide(workflow, item, {
        "challenge_id": "CH-1", "conversation_id": "CONV-1", "payload_hash": item["payload_hash"],
        "decision": "APPROVE", "evidence": "mock", "command_id": "CMD-EXPIRED",
    })
    assert response["acknowledgement"] == "CONSENT_EXPIRED"
    assert item["status"] == "CONSENT_EXPIRED"
    assert item["confirmation_record_id"] is None
    item["confirmation_record_id"] = "CONF-EXPIRED"
    item["confirmation_record_payload_hash"] = item["payload_hash"]
    item["confirmation_record_challenge_id"] = "CH-1"
    with pytest.raises(PermissionError, match="expired"):
        transaction_worker.execute(item, "normal")


def test_unknown_commit_reconciles_without_blind_retry():
    from app.gateways.commit_gateway import mock_bank

    _, item = consent_workflow()
    item["confirmation_record_id"] = "CONF-1"
    item["confirmation_record_payload_hash"] = item["payload_hash"]
    item["confirmation_record_challenge_id"] = "CH-1"
    item["idempotency_key"] = "idem-unknown-test"
    before_commits = len(mock_bank.commit_calls)
    before_status = len(mock_bank.reconciliation_calls)
    result = transaction_worker.execute(item, "unknown_completed")
    assert result["status"] == "UNKNOWN"
    assert item["status"] == "UNKNOWN"
    result = transaction_worker.reconcile(item, "unknown_completed")
    assert result["status"] == "COMPLETED"
    assert len(mock_bank.commit_calls) == before_commits + 1
    assert len(mock_bank.reconciliation_calls) == before_status + 1


def test_conversation_manager_rebuilds_projection_from_workflow():
    manager = ConversationManager()
    workflow = {
        "workflow_id": "WF-rebuild",
        "work_items": [{
            "work_item_id": "WI-1", "intent": "balance_inquiry", "status": "COMPLETED",
            "last_update": "2026-01-01T00:00:00+00:00",
        }],
    }
    projection = manager.rebuild_projection(workflow)
    assert projection["messages"][0]["status"] == "COMPLETED"
    assert manager.rebuild_projection(workflow)["messages"] == projection["messages"]

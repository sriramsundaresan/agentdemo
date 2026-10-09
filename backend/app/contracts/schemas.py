from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


class ConsentDecision(BaseModel):
    challenge_id: str
    conversation_id: str
    payload_hash: str
    decision: Literal["APPROVE", "REJECT"]
    evidence_method: Literal["MOCK_BIOMETRIC", "MOCK_PIN"] = "MOCK_BIOMETRIC"
    evidence: str = "synthetic-demo-evidence"
    command_id: str


class WorkflowCommand(BaseModel):
    command_id: str
    command_type: Literal["WORK_ITEM_CONSENT_APPROVED"]
    work_item_id: str
    challenge_id: str
    payload_hash: str
    confirmation_record_id: str


class WorkflowStartRequest(BaseModel):
    workflow: dict


class DeveloperControls(BaseModel):
    mode: Literal[
        "normal", "deny_policy", "require_consent", "reject_consent",
        "expire_consent", "bank_failure", "unknown_completed",
        "unknown_failed", "delay_events", "duplicate_events",
    ] = "normal"


class WorkItem(BaseModel):
    work_item_id: str
    intent: str
    type: Literal["read-only", "knowledge", "financial"]
    status: str
    dependencies: list[str] = Field(default_factory=list)
    agent_id: str | None = None
    policy_status: str
    consent_status: str
    transaction_status: str
    last_update: datetime
    prepared_payload: dict | None = None
    payload_hash: str | None = None
    confirmation_challenge_id: str | None = None
    confirmation_record_id: str | None = None
    bank_reference: str | None = None
    idempotency_key: str | None = None
    result: str | None = None


class WorkflowView(BaseModel):
    workflow_id: str
    conversation_id: str
    request_status: str
    work_items: list[WorkItem]
    processed_command_ids: list[str]
    created_at: datetime
    correlation_id: str


class ConsentPresentation(BaseModel):
    challenge_id: str
    work_item_id: str
    from_account: str
    beneficiary: str
    amount: Decimal
    currency: str
    fee: Decimal
    execution_date: str
    expires_at: datetime
    payload_hash: str
    synthetic: bool = True


class TraceEntry(BaseModel):
    event_id: str
    event_name: str
    caller: str
    executor: str
    contract: str
    correlation_id: str
    workflow_id: str | None = None
    work_item_id: str | None = None
    request_status: str
    response_status: str
    occurred_at: datetime


class ErrorResponse(BaseModel):
    schemaVersion: str = "1.0"
    errorId: str
    code: str
    category: str
    retryability: str
    customerAction: str | None = None
    correlationId: str

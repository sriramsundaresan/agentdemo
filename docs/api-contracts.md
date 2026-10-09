# API contracts

The FastAPI OpenAPI contract is available at `http://localhost:8000/docs` when the backend is running. Responses and seeded records are synthetic. Monetary values are decimal strings; no real customer credentials or bank endpoints are used.

## Channel message

`POST /api/conversations/{conversationId}/messages`

```json
{
  "message": "Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.",
  "conversation_id": "CONV-SYNTHETIC-001"
}
```

The response includes `schemaVersion`, `messageId`, `conversationId`, `workflowId`, `correlationId`, `traceId`, `occurredAt`, `requestStatus` and the accepted workflow state. `WORKFLOW_STARTED` means durable processing was accepted, not that a transaction completed.

## Workflow state and streaming

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/conversations/{conversationId}/workflows` | Restore durable demo workflows for the channel conversation |
| `GET` | `/api/conversations/{conversationId}/workflows/{workflowId}` | Read customer-visible workflow state through Conversation Manager |
| `GET` | `/api/conversations/{conversationId}/workflows/{workflowId}/events` | Subscribe to customer-visible Server-Sent Events |
| `GET` | `/api/conversations/{conversationId}/workflows/{workflowId}/trace` | Read chronological caller/executor trace |
| `GET` | `/api/workflows` | Internal list; requires Conversation Manager or Workflow Access identity |
| `GET` | `/api/workflows/{workflowId}` | Internal state query; requires Conversation Manager identity |
| `GET` | `/api/workflows/{workflowId}/events` | Internal event subscription; requires Conversation Manager identity |
| `GET` | `/api/workflows/{workflowId}/trace` | Internal trace query; requires Conversation Manager identity |
| `GET` | `/api/workflows/{workflowId}/customer-visible-state` | Internal projection query; requires mock service identity |
| `POST` | `/api/workflows` | Internal workflow start; requires `central-orchestrator` identity |
| `POST` | `/api/workflows/{workflowId}/commands` | Internal command; requires `confirmation-service` identity |
| `POST` | `/api/workflows/{workflowId}/cancel` | Internal cancel operation |

Workflow commands carry a unique `command_id`; duplicate IDs are acknowledged idempotently. The LocalWorkflowProvider implements the provider boundary for start, signal, query and cancel.

## Capability APIs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/capabilities/accounts/eligible` | List synthetic eligible accounts |
| `GET` | `/api/capabilities/accounts/{accountRef}/balance` | Read synthetic account balance |
| `POST` | `/api/capabilities/transfers/prepare` | Prepare and validate transfer details |
| `POST` | `/api/capabilities/bill-payments/prepare` | Prepare and validate bill-payment details |

The Specialist Agent is constructed with only the read/prepare gateway. It has no Commit Gateway dependency.

## Consent

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/confirmation-challenges` | Create a payload-hash-bound challenge (internal identity required) |
| `GET` | `/api/confirmation-challenges/{challengeId}/presentation` | Return masked transaction presentation and expiry |
| `POST` | `/api/confirmation-challenges/{challengeId}/decision` | Submit a structured decision directly to Confirmation Service |

Decision body:

```json
{
  "challenge_id": "CH-...",
  "payload_hash": "sha256-of-canonical-validated-payload",
  "decision": "APPROVE",
  "evidence_method": "MOCK_BIOMETRIC",
  "evidence": "synthetic-demo-evidence",
  "command_id": "CMD-unique-id"
}
```

The challenge ID must match the route, the hash must match the stored payload, and the challenge must be unexpired. The UI never sends a chat message such as “yes” to approve a transaction. Mock PIN/biometric evidence is simulated and is not authentication.

## Commit and reconciliation

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/commit/transfers` | Commit path; accepts only `X-Mock-Service-Identity: transaction-worker` |
| `POST` | `/api/commit/bill-payments` | Commit path; accepts only `transaction-worker` |
| `GET` | `/api/bank/transactions/{idempotencyKey}/status` | Bank-authoritative synthetic status lookup |

The deterministic Transaction Worker requires a Confirmation Record, matching payload hash, policy approval and completed dependencies before commit. It supplies a stable idempotency key. An `UNKNOWN` result triggers the status endpoint and never a blind second commit. The mock bank owns final status and references such as `MOCK-TXN-000001`.

## Common metadata and errors

Where relevant, contracts carry `schemaVersion`, message/event ID, conversation/workflow/work-item IDs, `correlationId`, `traceId` and `occurredAt`. Error responses follow this shape:

```json
{
  "schemaVersion": "1.0",
  "errorId": "err-001",
  "code": "CONSENT_EXPIRED",
  "category": "BUSINESS_VALIDATION",
  "retryability": "NOT_RETRYABLE",
  "customerAction": "RESTART_CONFIRMATION",
  "correlationId": "corr-001"
}
```

For this local mock, FastAPI returns HTTP error details with the corresponding business rule. Production should standardize the full envelope at the API boundary.

## Identity boundary

Internal routes use a demonstration `X-Mock-Service-Identity` header. The browser can call only channel-facing conversation, consent presentation/decision and SSE APIs; internal workflow and capability APIs reject browser calls without mock service identities. This header is not authentication. A production implementation must use OAuth 2.0/OIDC for user identity, workload identity for service-to-service authorization, and mTLS for protected internal calls.

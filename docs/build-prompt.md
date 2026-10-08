# Build Prompt: Conversational Banking Architecture Presentation and Web Mock

## Role

Act as a senior full-stack engineer and solution architect. Build a self-contained developer demo for a conversational banking platform based on the architecture described in `Conversational_Banking_Customer_Architecture_Summary.md`.

The output must include:

1. A browser-based architecture presentation with free horizontal and vertical scrolling.
2. A functional web mock replacing the mobile application for the initial prototype.
3. Mock backend services that demonstrate the final agreed runtime model.
4. Automated tests for the most important architecture rules.
5. Clear local run instructions.

Do not reduce this to static screenshots. Build an interactive, demonstrable solution.

---

# 1. Architecture rules that must not be changed

Implement these rules exactly.

## Request and workflow model

- One customer request creates one durable `RequestWorkflow`.
- One `RequestWorkflow` contains N work items.
- Do not create one workflow per intent.
- Work items can execute in parallel or in sequence based on dependencies.
- The workflow owns authoritative request and work-item state.

## Orchestration model

- Natural-language messages go through the `ConversationManager` and `CentralOrchestrator`.
- The `CentralOrchestrator` identifies candidate intents and proposes a work-item dependency graph.
- Pre-agent policy is evaluated before agent invocation.
- The `PolicyService` only returns decisions. The `PolicyService` must never invoke agents or start workflows.
- The `CentralOrchestrator` applies policy decisions and calls the `WorkflowAccessService` to start one workflow.

## Agent model

- A `SpecialistAgent` prepares one scoped work item at a time.
- The agent may call Read and Prepare/Validate capability APIs.
- The agent must not call Commit APIs.
- The agent finishes preparation before customer consent is requested.
- The agent must not remain active while waiting for consent.

## Consent model

- Every financial work item has its own consent challenge.
- A conversational “yes” must not authorize a financial transaction.
- The `ConfirmationService` creates and validates consent challenges.
- Consent must be bound to the exact validated payload using a payload hash.
- Structured consent approval bypasses the `CentralOrchestrator`.
- Consent approval flows through the `ConfirmationService` and `WorkflowAccessService` to the existing workflow.

## Execution model

- The `RequestWorkflow` waits durably for consent.
- After valid consent, the workflow invokes deterministic transaction execution.
- A deterministic `TransactionWorker`, not an LLM agent, calls the Commit Gateway.
- The mock Bank API owns authoritative transaction status and reference.
- Unknown transaction status must not be presented as failure or success.

## UI and status model

- The `ConversationManager` listens to customer-visible workflow events.
- The `ConversationManager` maintains a customer-facing status projection.
- The `ConversationManager` prepares channel-neutral UI responses for status and consent presentation.
- The web application owns visual rendering.
- Workflow events travel asynchronously to the `ConversationManager`.
- Structured customer actions travel back as workflow commands.

---

# 2. Required technology stack

Use this default stack unless the repository already contains an equivalent approved stack.

## Frontend

- React
- TypeScript
- Vite
- React Router
- CSS modules or plain CSS variables
- Mermaid for architecture and sequence diagrams
- EventSource for Server-Sent Events
- No external design system is required

## Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy
- SQLite for the local mock
- Server-Sent Events for workflow status streaming
- In-process asynchronous event bus for the first implementation
- Provider interfaces so SQLite and the in-process bus can later be replaced

## Testing

- Pytest for backend tests
- Vitest and React Testing Library for frontend tests
- Playwright for one end-to-end happy path

## Packaging

- Dockerfiles for frontend and backend
- `docker-compose.yml`
- `.env.example`
- A root `README.md`

If the environment cannot support the preferred stack, use an equivalent stack but preserve all API and architecture boundaries.

---

# 3. Repository structure

Create the following structure:

```text
conversational-banking-mock/
├── README.md
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── architecture-summary.md
│   ├── api-contracts.md
│   └── demo-script.md
├── presentation/
│   ├── index.html
│   ├── styles.css
│   ├── presentation.js
│   └── content/
│       └── architecture-summary.md
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── models/
│   │   └── styles/
│   └── tests/
└── backend/
    ├── pyproject.toml
    ├── app/
    │   ├── main.py
    │   ├── api/
    │   ├── contracts/
    │   ├── services/
    │   ├── workflow/
    │   ├── agents/
    │   ├── gateways/
    │   ├── events/
    │   ├── persistence/
    │   └── seed/
    └── tests/
```

Copy the supplied architecture Markdown into:

```text
docs/architecture-summary.md
presentation/content/architecture-summary.md
```

---

# 4. Architecture presentation requirements

Build a standalone HTML presentation under `/presentation`.

## Navigation

Provide tabs or sections for:

1. Platform overview
2. Component responsibilities
3. One request and N work items
4. Natural-language request sequence
5. Work-item preparation and consent sequence
6. Consent approval and workflow-resume sequence
7. Request and response statuses
8. Caller, executor and state owner
9. API contracts
10. Technology mapping

## Scrolling and usability

- Allow free horizontal and vertical scrolling.
- Provide a collapsible header.
- Provide a maximize-diagram mode.
- Freeze participant boxes or swimlane headers while scrolling vertically.
- Keep lane labels visible while scrolling horizontally when practical.
- Provide zoom controls: 75%, 100%, 125% and Fit Width.
- Provide a reset-view button.
- Provide light and dark mode.
- Provide print-friendly styles.
- Do not constrain diagrams to slide-sized pages.

## Markdown usage

Use the Markdown file as the source of truth for narrative content.

Render:

- Headings
- Paragraphs
- Tables
- Callouts
- Code blocks
- Mermaid diagrams

It is acceptable to preprocess the Markdown at build time. Do not require an internet connection at runtime.

## Presentation visual rules

Use consistent colors:

- Blue: conversation, planning and read-only operations
- Amber: policy, consent and customer action required
- Purple: workflow and asynchronous events
- Green: deterministic execution and authoritative bank results
- Gray: waiting or blocked
- Red: denied, failed or unknown status

Each diagram must label:

- Caller
- Executor
- Request or command
- Immediate response
- Asynchronous event where applicable
- Authoritative state owner

---

# 5. Web mock user experience

Create a web banking prototype with three primary panes.

## Left pane: Conversation

Show:

- Customer messages
- Assistant responses
- Timestamps
- System status messages
- Input box
- Send button
- Sample request buttons

Sample requests:

```text
Check my balance.
```

```text
Transfer THB 10,000 from my savings account to Somchai.
```

```text
Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.
```

```text
What is today's transfer limit?
```

## Center pane: Work-item status

Show one workflow card containing N work items.

Each work item displays:

- Work-item ID
- Intent
- Type: read-only, knowledge or financial
- Current status
- Dependency
- Agent assigned
- Policy status
- Consent status
- Transaction status
- Last update

Use semantic statuses, not fabricated percentages:

```text
RECEIVED
POLICY_CHECK
READY
PREPARING
VALIDATING
AWAITING_CONSENT
CONFIRMED
EXECUTING
BLOCKED_BY_DEPENDENCY
COMPLETED
FAILED
UNKNOWN
CONSENT_REJECTED
CONSENT_EXPIRED
```

## Right pane: Technical trace

Show a chronological technical trace containing:

- Caller
- Executor
- Contract or event name
- Correlation ID
- Workflow ID
- Work-item ID
- Request status
- Response status
- Timestamp

Allow filtering by:

- Work item
- Component
- Calls
- Returns
- Events
- Errors

---

# 6. Consent UI

When a financial work item reaches `AWAITING_CONSENT`, show a modal or side panel.

The consent component must display:

- From account, masked
- Beneficiary, masked
- Amount
- Currency
- Fee
- Execution date
- Challenge ID
- Consent expiry countdown
- Confirm button
- Reject button
- Modify request button

For the mock, simulate biometric or PIN with a modal:

```text
Mock approval method:
[ Approve with mock biometric ]
[ Enter mock PIN ]
```

Clearly label the mechanism as simulated.

The web client must submit a structured consent decision to:

```text
POST /api/confirmation-challenges/{challengeId}/decision
```

The consent button must not post a chat message such as “yes”.

---

# 7. Mock scenarios

## Scenario A: Read-only balance inquiry

Expected result:

```text
RECEIVED → POLICY_CHECK → PREPARING → VALIDATING → COMPLETED
```

No consent is required.

Return a synthetic balance clearly marked as mock data.

## Scenario B: Single funds transfer

Expected result:

```text
RECEIVED
→ POLICY_CHECK
→ PREPARING
→ VALIDATING
→ AWAITING_CONSENT
→ CONFIRMED
→ EXECUTING
→ COMPLETED
```

## Scenario C: Multiple intents

Input:

```text
Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.
```

Create:

```text
WI-1 Balance inquiry
WI-2 Funds transfer
WI-3 Bill payment, dependent on WI-2 = COMPLETED
```

Behavior:

- WI-1 and WI-2 may prepare in parallel.
- WI-3 starts as `BLOCKED_BY_DEPENDENCY`.
- WI-2 requires Consent Challenge 1.
- After WI-2 completes, WI-3 becomes `READY`.
- WI-3 is validated again after the dependency completes.
- WI-3 requires Consent Challenge 2.
- The workflow remains one workflow instance throughout.

## Scenario D: Consent rejected

Expected result:

```text
WI-2: CONSENT_REJECTED
WI-3: BLOCKED_BY_DEPENDENCY
```

Independent work items remain completed.

## Scenario E: Consent expired

Use a configurable short expiry for the demo.

Expected result:

```text
AWAITING_CONSENT → CONSENT_EXPIRED
```

Do not execute the transaction.

## Scenario F: Unknown transaction result

Provide a developer toggle that causes the mock bank commit call to return `UNKNOWN`.

The workflow must:

- Set the work item to `UNKNOWN`.
- Show “Checking transaction status” to the user.
- Invoke the mock transaction-status endpoint.
- Resolve the status deterministically.
- Never blindly retry the commit operation.

---

# 8. Required mock services

Implement the following logical services as separate modules. They may run in one FastAPI process for the prototype, but the boundaries must be visible in code and APIs.

## Conversation Manager

Responsibilities:

- Accept customer messages from the Channel Gateway route.
- Call the Central Orchestrator.
- Store conversation state.
- Subscribe to customer-visible workflow events.
- Build status and consent response models.
- Expose SSE stream for the browser.

## Central Orchestrator

Responsibilities:

- Parse the sample requests into configured intents.
- Create candidate work items.
- Create dependency edges.
- Call pre-agent policy.
- Apply policy decisions.
- Call Workflow Access Service to start one workflow.

For the mock, deterministic parsing rules are acceptable. Do not require a real LLM.

## Policy Service

Return deterministic policy decisions.

Examples:

- Balance inquiry: permit read.
- Transfer: permit prepare; deny commit to agent.
- Bill payment: permit prepare; require separate consent.
- Commit: permit only for the transaction worker and valid Confirmation Record.

The Policy Service must not call any other service.

## Request Workflow

Implement one workflow object per customer request.

The workflow contains:

```python
workflow_id
conversation_id
request_status
work_items[]
processed_command_ids[]
```

Each work item contains:

```python
work_item_id
intent
type
status
dependencies[]
agent_id
policy_decision_id
validation_reference
confirmation_challenge_id
confirmation_record_id
idempotency_key
bank_reference
error_code
```

The workflow must persist state in SQLite so browser refresh or backend restart can recover demo state.

## Specialist Agent

Use deterministic handlers for:

- Balance inquiry
- Funds-transfer preparation
- Bill-payment preparation
- Knowledge question

The agent may call only Read and Prepare Capability Gateway operations.

## Read/Prepare Capability Gateway

Provide endpoints such as:

```text
GET  /api/capabilities/accounts/eligible
GET  /api/capabilities/accounts/{accountRef}/balance
POST /api/capabilities/transfers/prepare
POST /api/capabilities/bill-payments/prepare
```

Return mock records clearly marked as synthetic.

## Confirmation Service

Provide:

```text
POST /api/confirmation-challenges
GET  /api/confirmation-challenges/{challengeId}/presentation
POST /api/confirmation-challenges/{challengeId}/decision
```

Responsibilities:

- Create challenge.
- Compute canonical payload hash.
- Validate challenge, customer, expiry and decision.
- Simulate validation of mock biometric/PIN evidence.
- Create Confirmation Record.
- Call Workflow Access Service with a consent command.

## Workflow Access Service

Provide:

```text
POST /api/workflows
POST /api/workflows/{workflowId}/commands
GET  /api/workflows/{workflowId}/customer-visible-state
POST /api/workflows/{workflowId}/cancel
```

Responsibilities:

- Validate caller identity in the mock using service headers.
- Validate command schema.
- Deduplicate `commandId`.
- Resolve workflow instance.
- Start, signal, query or cancel workflow.
- Return acknowledgement.

Use an interface such as:

```python
class WorkflowProvider:
    def start_workflow(...): ...
    def send_command(...): ...
    def query_state(...): ...
    def cancel_workflow(...): ...
```

Implement `LocalWorkflowProvider` for the mock.

## Transaction Worker

Responsibilities:

- Verify policy reference.
- Verify Confirmation Record.
- Verify payload hash.
- Verify dependency state.
- Generate or use stable idempotency key.
- Call Commit Gateway.

## Commit Gateway and Mock Bank API

Provide:

```text
POST /api/commit/transfers
POST /api/commit/bill-payments
GET  /api/bank/transactions/{idempotencyKey}/status
```

The Commit Gateway accepts calls only from the mock transaction-worker identity.

Return synthetic bank references such as:

```text
MOCK-TXN-000001
```

Always label values and references as mock data in the UI.

## Event Backbone

Implement publish/subscribe interfaces.

Events required:

```text
request.workflow.started
workitem.preparing
workitem.validating
workitem.awaiting_consent
workitem.consent_received
workitem.executing
workitem.blocked
workitem.completed
workitem.failed
workitem.unknown
request.workflow.completed
request.workflow.partial_failure
```

The Conversation Manager subscribes to customer-visible events and pushes them to the browser using SSE.

---

# 9. API contracts

Use Pydantic models and generate OpenAPI documentation.

All contracts must contain, where relevant:

```text
schemaVersion
messageId or eventId
conversationId
workflowId
workItemId
correlationId
traceId
occurredAt
```

Use a common error format:

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

Use `Decimal` or string representation for money. Do not use binary floating-point for financial amounts.

---

# 10. Security simulation

This is a mock, but architecture boundaries must remain visible.

Use mock service identities through headers:

```text
X-Mock-Service-Identity: conversation-manager
X-Mock-Service-Identity: confirmation-service
X-Mock-Service-Identity: transaction-worker
```

Enforce:

- Specialist Agent cannot call Commit endpoints.
- Confirmation Service can send consent commands.
- Transaction Worker can call Commit Gateway.
- Browser cannot call internal workflow APIs directly.
- Consent decision must contain the expected challenge ID and payload hash.

Do not implement real authentication secrets. Document where OAuth 2.0, OIDC, workload identity and mTLS would be used in production.

---

# 11. Developer controls

Add a developer panel with toggles for:

- Normal execution
- Deny pre-agent policy
- Require consent
- Reject consent
- Expire consent
- Bank commit failure
- Bank result unknown, then completed
- Bank result unknown, then failed
- Event delivery delay
- Duplicate event delivery

These controls must visibly demonstrate idempotency, deduplication and recovery behavior.

---

# 12. Required tests

At minimum, implement tests proving:

1. One request creates one workflow with N work items.
2. Policy Service does not start a workflow.
3. Specialist Agent cannot call Commit Gateway.
4. Financial work item cannot execute without Confirmation Record.
5. Payload-hash mismatch blocks execution.
6. Duplicate consent command is idempotent.
7. Duplicate workflow event does not create duplicate UI messages.
8. Dependent bill payment remains blocked until transfer is `COMPLETED`.
9. Consent rejection prevents execution.
10. Consent expiry prevents execution.
11. Unknown commit result invokes status reconciliation instead of blind retry.
12. Conversation Manager can rebuild its projection from workflow state.

---

# 13. Demo script

Create `docs/demo-script.md` covering this demonstration:

1. Open the web mock.
2. Submit the multi-intent request.
3. Show one workflow with three work items.
4. Show balance and transfer preparation occurring in parallel.
5. Show bill payment blocked by transfer.
6. Show transfer consent UI.
7. Approve with mock biometric.
8. Show immediate `CONSENT_RECEIVED` acknowledgement.
9. Show transfer move to `EXECUTING`, then `COMPLETED`.
10. Show bill payment become `READY`.
11. Show separate bill-payment consent.
12. Complete bill payment.
13. Show final request summary.
14. Open technical trace and point out callers and executors.
15. Repeat using `UNKNOWN` transaction mode and show reconciliation.

---

# 14. Acceptance criteria

The solution is complete only when:

- The architecture presentation opens locally in a browser.
- The presentation supports free vertical and horizontal scrolling.
- Diagram participants remain visible during vertical scrolling.
- The header can be collapsed.
- The web mock runs locally.
- A user can submit the provided multi-intent request.
- Exactly one workflow is created.
- The workflow contains three work items.
- The user can approve two separate consent challenges.
- Structured consent bypasses the Orchestrator.
- The UI receives asynchronous workflow-status updates.
- The final bank references are visibly marked as synthetic.
- The technical trace clearly shows caller, executor, contract and state owner.
- Tests pass.
- README contains exact run commands.

---

# 15. Deliverables

Return the complete repository with:

```text
README.md
architecture HTML presentation
React web mock
FastAPI mock backend
OpenAPI documentation
automated tests
Docker Compose configuration
demo script
architecture decision notes
```

Do not return only design guidance. Implement the working mock.

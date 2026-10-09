# Architecture decision: durable request workflow and consent-gated execution

**Status:** Accepted for the local mock  
**Decision scope:** Prototype runtime boundaries; synthetic data only

## Context

One customer utterance may express multiple banking intents with independent preparation and dependencies. A financial operation must not be committed based on natural-language confirmation alone, and an LLM agent must not have access to commit APIs. Workflow and bank transaction status have separate authoritative owners.

## Decision

- A customer request creates exactly one durable `RequestWorkflow` containing N work items and explicit dependency edges.
- Natural-language input passes through Conversation Manager and Central Orchestrator. Pre-agent Policy Service returns decisions only; it never invokes an agent or starts a workflow.
- Specialist Agents handle one scoped work item and can only use read/prepare capabilities. Preparation completes before any consent wait.
- Confirmation Service creates an independent challenge per financial work item and binds approval to the canonical validated payload hash.
- Structured consent bypasses the Orchestrator and signals the existing workflow through Workflow Access Service.
- A deterministic Transaction Worker validates policy, confirmation, hash and dependencies before calling Commit Gateway. The mock Bank API owns authoritative transaction status and references.
- An `UNKNOWN` commit outcome is reconciled using the bank status endpoint. The commit is never blindly retried.
- Workflow state persists in SQLite. The first implementation uses an in-process asynchronous event bus and LocalWorkflowProvider; provider interfaces keep workflow and event infrastructure replaceable.

## Consequences

The architecture is testable without a real model, banking system, or workflow engine. The local SQLite database and event bus are not a multi-replica production deployment; replacing them must preserve command idempotency, event identity, payload binding and workflow durability. Mock headers and simulated biometric/PIN evidence provide no real security.

## Production follow-up

Use OAuth 2.0/OIDC for customer identity, workload identities and mTLS for services, a bank-approved secrets/HSM platform, a durable workflow engine and event backbone, and bank-owned validation/commit/status APIs. Production policy and confirmation evidence storage require bank security, audit and compliance review.

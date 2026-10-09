# Demo script

Use only the local prototype. All displayed customer, account, balance, amount, bank references and approval evidence are synthetic; no financial operation reaches a real bank.

1. Start FastAPI and Vite using the commands in the root README. Open `http://localhost:5173`.
2. Open **Developer controls** and leave the scenario in **Normal execution**.
3. Submit: “Check my balance, transfer THB 10,000 to Somchai, then pay my electricity bill.”
4. Point out that one `WF-…` Request Workflow contains WI-1, WI-2 and WI-3—not three workflows.
5. Show WI-1 balance inquiry completed while WI-2 transfer is prepared for consent; these independent items can prepare in parallel.
6. Show WI-3 in `BLOCKED_BY_DEPENDENCY` until WI-2 completes authoritatively.
7. Open **Review consent** for WI-2. Identify the masked synthetic accounts, amount, fee, challenge ID, expiry and simulated-only auth selector.
8. Choose **Approve with mock biometric**. The structured decision posts the challenge ID and payload hash directly to Confirmation Service; it does not add “yes” to chat or call the Orchestrator.
9. Point out the immediate `CONSENT_RECEIVED` acknowledgement, then watch asynchronous status events move the item through `EXECUTING` and `COMPLETED`.
10. Show WI-3 become `AWAITING_CONSENT` only after the transfer is complete and its dependent validation is performed.
11. Approve WI-3 using its independent challenge. Confirm the unique challenge and bank reference.
12. Review the final request summary and the visibly synthetic `MOCK-TXN-…` references.
13. Open **Technical trace**. Filter by work item, component, calls, returns, events or errors. Identify caller, executor, contract, correlation ID, workflow ID and state owner.
14. Start a fresh request using **Unknown → completed** in Developer controls.
15. Approve the transfer. Show `UNKNOWN` / “Checking transaction status”, then status reconciliation to the deterministic bank outcome. Explain that the worker does one commit call and does not blindly retry.

Optional variations: **Reject consent**, **Expire consent**, **Deny pre-agent policy**, **Bank commit failure**, **Unknown → failed**, **Delay event delivery** and **Duplicate event delivery**. The latter demonstrates event-ID deduplication in the Conversation Manager projection.

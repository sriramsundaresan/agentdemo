from app.workflow.provider import workflow_provider


class WorkflowAccessService:
    def start(self, workflow: dict, identity: str):
        if identity not in {"central-orchestrator", "conversation-manager"}:
            raise PermissionError("Caller is not allowed to start a workflow")
        return workflow_provider.start_workflow(workflow)

    def consent_command(self, workflow: dict, command: dict, identity: str):
        if identity != "confirmation-service":
            raise PermissionError("Only Confirmation Service may send consent commands")
        item = next(
            (entry for entry in workflow["work_items"] if entry["work_item_id"] == command["work_item_id"]),
            None,
        )
        if (
            item is None
            or item.get("confirmation_challenge_id") != command["challenge_id"]
            or item.get("confirmation_record_id") != command["confirmation_record_id"]
            or item.get("confirmation_record_payload_hash") != command["payload_hash"]
        ):
            raise ValueError("Consent command does not match the validated work item")
        if command["command_id"] in workflow["processed_command_ids"]:
            return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": True}
        return workflow_provider.send_command(workflow, command)

    def query(self, workflow):
        return workflow_provider.query_state(workflow)


workflow_access_service = WorkflowAccessService()

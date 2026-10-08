from app.workflow.provider import workflow_provider


class WorkflowAccessService:
    def start(self, workflow: dict, identity: str):
        if identity not in {"central-orchestrator", "conversation-manager"}:
            raise PermissionError("Caller is not allowed to start a workflow")
        return workflow_provider.start_workflow(workflow)

    def consent_command(self, workflow: dict, command: dict, identity: str):
        if identity != "confirmation-service":
            raise PermissionError("Only Confirmation Service may send consent commands")
        if command["command_id"] in workflow["processed_command_ids"]:
            return {"acknowledgement": "CONSENT_RECEIVED", "duplicate": True}
        return workflow_provider.send_command(workflow, command)

    def query(self, workflow):
        return workflow_provider.query_state(workflow)


workflow_access_service = WorkflowAccessService()

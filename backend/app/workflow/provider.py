from abc import ABC, abstractmethod


class WorkflowProvider(ABC):
    @abstractmethod
    def start_workflow(self, workflow): ...

    @abstractmethod
    def send_command(self, workflow, command): ...

    @abstractmethod
    def query_state(self, workflow): ...

    @abstractmethod
    def cancel_workflow(self, workflow): ...


class LocalWorkflowProvider(WorkflowProvider):
    def start_workflow(self, workflow):
        return workflow

    def send_command(self, workflow, command):
        workflow["processed_command_ids"].append(command["command_id"])
        return {"acknowledgement": "CONSENT_RECEIVED"}

    def query_state(self, workflow):
        return workflow

    def cancel_workflow(self, workflow):
        workflow["request_status"] = "CANCELLED"
        return workflow


workflow_provider = LocalWorkflowProvider()

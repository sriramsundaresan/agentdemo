from dataclasses import asdict, dataclass


@dataclass
class RequestWorkflow:
    workflow_id: str
    conversation_id: str
    request_status: str
    work_items: list[dict]
    processed_command_ids: list[str]
    created_at: str
    correlation_id: str
    original_message: str
    mode: str

    @classmethod
    def from_dict(cls, value: dict):
        workflow = cls(**value)
        ids = [item["work_item_id"] for item in workflow.work_items]
        if len(ids) != len(set(ids)):
            raise ValueError("Work-item IDs must be unique within a workflow")
        known_ids = set(ids)
        if any(dependency not in known_ids for item in workflow.work_items for dependency in item["dependencies"]):
            raise ValueError("Work-item dependencies must reference items in the same workflow")
        return workflow

    def to_dict(self):
        return asdict(self)

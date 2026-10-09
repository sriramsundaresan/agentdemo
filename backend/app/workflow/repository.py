from datetime import datetime, timezone

from app.persistence.models import WorkflowRecord
from sqlalchemy.orm.attributes import flag_modified


class WorkflowRepository:
    def __init__(self, session):
        self.session = session

    def add_workflow(self, workflow: dict):
        record = WorkflowRecord(
            id=workflow["workflow_id"], conversation_id=workflow["conversation_id"],
            request_status=workflow["request_status"], data=workflow,
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def get(self, workflow_id: str):
        return self.session.get(WorkflowRecord, workflow_id)

    def save(self, record: WorkflowRecord):
        record.request_status = record.data["request_status"]
        record.updated_at = datetime.now(timezone.utc)
        flag_modified(record, "data")
        self.session.commit()
        return record

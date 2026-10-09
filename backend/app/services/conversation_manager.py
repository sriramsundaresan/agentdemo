from datetime import datetime, timezone
from uuid import uuid4

from app.events.bus import event_bus


class ConversationManager:
    def __init__(self):
        self.projections: dict[str, dict] = {}

    async def project_event(self, event: dict):
        projection = self.projections.setdefault(event["workflow_id"], {"messages": [], "seen": set()})
        if event["event_id"] in projection["seen"]:
            return
        projection["seen"].add(event["event_id"])
        projection["messages"].append({
            "message_id": event["event_id"], "text": event.get("message", event["event_name"]),
            "status": event["response_status"], "occurred_at": event["occurred_at"],
        })

    def rebuild_projection(self, workflow: dict):
        projection = self.projections.setdefault(workflow["workflow_id"], {"messages": [], "seen": set()})
        for item in workflow["work_items"]:
            message_id = f"{workflow['workflow_id']}:{item['work_item_id']}:{item['status']}"
            if message_id not in projection["seen"]:
                projection["seen"].add(message_id)
                projection["messages"].append({
                    "message_id": message_id,
                    "text": f"{item['intent'].replace('_', ' ').title()}: {item['status']}",
                    "status": item["status"],
                    "occurred_at": item["last_update"],
                })
        return projection

    async def emit(self, workflow_id: str, event_name: str, response_status: str,
                   *, work_item_id: str | None = None, caller: str = "Request Workflow",
                   executor: str = "Conversation Manager", contract: str = "WorkflowStatusEvent",
                   message: str | None = None, mode: str = "normal",
                   conversation_id: str | None = None):
        now = datetime.now(timezone.utc).isoformat()
        event = {
            "schema_version": "1.0", "event_id": str(uuid4()), "event_name": event_name,
            "conversation_id": conversation_id, "trace_id": str(uuid4()), "caller": caller,
            "executor": executor, "contract": contract, "correlation_id": workflow_id,
            "workflow_id": workflow_id, "work_item_id": work_item_id,
            "request_status": response_status, "response_status": response_status,
            "occurred_at": now, "message": message,
        }
        await event_bus.publish(
            event,
            duplicate=mode == "duplicate_events",
            delay=0.5 if mode == "delay_events" else 0,
        )
        return event


conversation_manager = ConversationManager()
event_bus.subscribe_handler(conversation_manager.project_event)

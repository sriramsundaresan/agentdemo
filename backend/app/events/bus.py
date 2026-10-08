import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4


class EventBus:
    def __init__(self):
        self.subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self.history: list[dict] = []

    async def publish(self, event: dict, *, duplicate: bool = False, delay: float = 0):
        if delay:
            await asyncio.sleep(delay)
        event.setdefault("event_id", str(uuid4()))
        event.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
        self.history.append(event)
        for queue in tuple(self.subscribers[event["workflow_id"]]):
            queue.put_nowait(event)
            if duplicate:
                queue.put_nowait(event)

    def subscribe(self, workflow_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers[workflow_id].add(queue)
        return queue

    def unsubscribe(self, workflow_id: str, queue: asyncio.Queue):
        self.subscribers[workflow_id].discard(queue)


event_bus = EventBus()

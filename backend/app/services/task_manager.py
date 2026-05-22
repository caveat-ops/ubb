import json
import time
import uuid
from typing import Optional


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._messages: dict[str, list[dict]] = {}
    
    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "id": task_id,
            "status": "running",
            "created_at": time.time(),
        }
        self._messages[task_id] = []
        return task_id
    
    def add_message(self, task_id: str, msg: dict):
        if task_id in self._messages:
            self._messages[task_id].append(msg)
    
    def get_messages(self, task_id: str, since_index: int = 0) -> tuple[list[dict], int]:
        msgs = self._messages.get(task_id, [])
        return msgs[since_index:], len(msgs)
    
    def complete(self, task_id: str, success: bool = True, error: Optional[str] = None):
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "completed" if success else "error"
            self._tasks[task_id]["error"] = error
        self.add_message(task_id, {"type": "complete" if success else "error", "error": error})
    
    def get_status(self, task_id: str) -> Optional[str]:
        task = self._tasks.get(task_id)
        return task["status"] if task else None


task_manager = TaskManager()

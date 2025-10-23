"""自然言語タスク管理。"""
from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from core.state import Blackboard


class TaskState(str, Enum):
    NEW = "new"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELED = "canceled"
    DONE = "done"


@dataclass
class Task:
    id: str
    description: str
    state: TaskState = TaskState.NEW
    history: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"タスク[{self.id}] {self.description} 状態={self.state}"


class TaskManager:
    def __init__(self, log_dir: Path, blackboard: Optional[Blackboard] = None) -> None:
        self._tasks: Dict[str, Task] = {}
        self._log_path = log_dir / "tasks.log"
        log_dir.mkdir(parents=True, exist_ok=True)
        if not self._log_path.exists():
            self._log_path.write_text("timestamp,task_id,state,message\n", encoding="utf-8")
        self._blackboard = blackboard

    def _log(self, task: Task, message: str) -> None:
        timestamp = datetime.now().isoformat()
        with self._log_path.open("a", encoding="utf-8", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow([timestamp, task.id, task.state.value, message])
        task.history.append(message)

    def _update_blackboard(self, task: Optional[Task]) -> None:
        if not self._blackboard:
            return
        self._blackboard.current_task = task.description if task else None

    def create_task(self, description: str, reason: str) -> Task:
        task_id = uuid.uuid4().hex[:8]
        task = Task(id=task_id, description=description)
        self._tasks[task_id] = task
        summary = f"新規タスク: '{description}' を登録。根拠: {reason}"
        self._log(task, summary)
        self._update_blackboard(task)
        return task

    def start_task(self, task_id: str, reason: str) -> Task:
        task = self._tasks[task_id]
        if task.state not in (TaskState.NEW, TaskState.PAUSED):
            raise ValueError("start_task は new もしくは paused からのみ遷移可能です")
        task.state = TaskState.RUNNING
        summary = f"タスク開始: '{task.description}'。根拠: {reason}"
        self._log(task, summary)
        self._update_blackboard(task)
        return task

    def pause_task(self, task_id: str, reason: str) -> Task:
        task = self._tasks[task_id]
        if task.state != TaskState.RUNNING:
            raise ValueError("pause_task は running からのみ遷移可能です")
        task.state = TaskState.PAUSED
        self._log(task, f"タスク一時停止: '{task.description}'。理由: {reason}")
        self._update_blackboard(task)
        return task

    def cancel_task(self, task_id: str, reason: str) -> Task:
        task = self._tasks[task_id]
        if task.state in (TaskState.CANCELED, TaskState.DONE):
            raise ValueError("既に完了または中止済みのタスクです")
        task.state = TaskState.CANCELED
        self._log(task, f"タスク中止: '{task.description}'。理由: {reason}")
        self._update_blackboard(None)
        return task

    def complete_task(self, task_id: str, reason: str) -> Task:
        task = self._tasks[task_id]
        if task.state != TaskState.RUNNING:
            raise ValueError("complete_task は running からのみ遷移可能です")
        task.state = TaskState.DONE
        self._log(task, f"タスク完了: '{task.description}'。成果: {reason}")
        self._update_blackboard(None)
        return task

    def get_task(self, task_id: str) -> Task:
        return self._tasks[task_id]

    def current_task(self) -> Optional[Task]:
        for task in self._tasks.values():
            if task.state == TaskState.RUNNING:
                return task
        return None

    def describe(self) -> str:
        lines = [task.summary() for task in self._tasks.values()]
        return "\n".join(lines)

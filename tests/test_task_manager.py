from pathlib import Path

from core.state import Blackboard
from tasks.manager import TaskManager, TaskState


def test_task_state_transitions(tmp_path: Path):
    bb = Blackboard()
    manager = TaskManager(tmp_path, blackboard=bb)
    task = manager.create_task("木を1本集める", "テスト")
    assert task.state == TaskState.NEW
    assert bb.current_task == "木を1本集める"

    task = manager.start_task(task.id, "開始")
    assert task.state == TaskState.RUNNING
    assert bb.current_task == "木を1本集める"

    task = manager.complete_task(task.id, "完了")
    assert task.state == TaskState.DONE
    assert bb.current_task is None

    log_text = (tmp_path / "tasks.log").read_text(encoding="utf-8")
    assert "木を1本集める" in log_text
    assert "タスク完了" in log_text

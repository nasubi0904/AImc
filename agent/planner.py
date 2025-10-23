"""簡易プランナー。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

from agent.bt import BehaviorTree, build_default_tree
from core.state import Blackboard

if TYPE_CHECKING:  # pragma: no cover
    from tasks.manager import TaskManager


@dataclass
class Skill:
    name: str
    description: str

    def build_tree(self) -> BehaviorTree:
        raise NotImplementedError


class ForwardSkill(Skill):
    def build_tree(self) -> BehaviorTree:
        return build_default_tree()


class StopSkill(Skill):
    def build_tree(self) -> BehaviorTree:
        from agent.bt import ActionNode, stop_action

        return BehaviorTree(ActionNode(stop_action))


class Planner:
    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {
            "forward": ForwardSkill(name="forward", description="前進する"),
            "stop": StopSkill(name="stop", description="停止"),
        }
        self._task_manager: Optional["TaskManager"] = None

    def bind_task_manager(self, manager: "TaskManager") -> None:
        self._task_manager = manager

    def select(self, goal: str) -> Skill:
        return self._skills.get(goal, self._skills["forward"])

    def _goal_from_tasks(self, default: str) -> str:
        if not self._task_manager:
            return default
        task = self._task_manager.current_task()
        if not task:
            return default
        text = task.description
        if "止" in text:
            return "stop"
        return default

    def plan(self, goal: str, blackboard: Blackboard) -> BehaviorTree:
        effective_goal = self._goal_from_tasks(goal)
        skill = self.select(effective_goal)
        return skill.build_tree()

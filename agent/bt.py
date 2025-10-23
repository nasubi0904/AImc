"""簡易ビヘイビアツリー実装。"""
from __future__ import annotations

from enum import Enum, auto
from typing import Callable, List

from control.input import InputController
from core.state import Blackboard


class Status(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    RUNNING = auto()


class Node:
    def tick(self, blackboard: Blackboard, inputs: InputController) -> Status:
        raise NotImplementedError


class ActionNode(Node):
    def __init__(self, action: Callable[[Blackboard, InputController], Status]) -> None:
        self._action = action

    def tick(self, blackboard: Blackboard, inputs: InputController) -> Status:
        return self._action(blackboard, inputs)


class Sequence(Node):
    def __init__(self, nodes: List[Node]) -> None:
        self._nodes = nodes

    def tick(self, blackboard: Blackboard, inputs: InputController) -> Status:
        for node in self._nodes:
            status = node.tick(blackboard, inputs)
            if status != Status.SUCCESS:
                return status
        return Status.SUCCESS


class Selector(Node):
    def __init__(self, nodes: List[Node]) -> None:
        self._nodes = nodes

    def tick(self, blackboard: Blackboard, inputs: InputController) -> Status:
        for node in self._nodes:
            status = node.tick(blackboard, inputs)
            if status != Status.FAILURE:
                return status
        return Status.FAILURE


def move_forward_action(blackboard: Blackboard, inputs: InputController) -> Status:
    inputs.press("w")
    blackboard.record_reason("前進する理由: 既定の探索")
    return Status.RUNNING


def turn_right_action(blackboard: Blackboard, inputs: InputController) -> Status:
    inputs.press("d")
    blackboard.record_reason("右へ向きを変える")
    return Status.RUNNING


def stop_action(blackboard: Blackboard, inputs: InputController) -> Status:
    inputs.release("w")
    inputs.release("d")
    blackboard.record_reason("停止: 条件を満たした")
    return Status.SUCCESS


class BehaviorTree:
    def __init__(self, root: Node) -> None:
        self._root = root

    def tick(self, blackboard: Blackboard, inputs: InputController) -> Status:
        return self._root.tick(blackboard, inputs)


def build_default_tree() -> BehaviorTree:
    forward = ActionNode(move_forward_action)
    turn = ActionNode(turn_right_action)
    stop = ActionNode(stop_action)
    root = Selector([forward, turn, stop])
    return BehaviorTree(root)

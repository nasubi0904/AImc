"""ブラックボードと観測データの定義。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

try:  # pragma: no cover - numpy が無い環境でも動かすため
    import numpy as np
except Exception:  # noqa: BLE001
    np = None  # type: ignore

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float
    z: float


class HudStatus(BaseModel):
    hp: int = Field(default=20, ge=0, le=20)
    hunger: int = Field(default=20, ge=0, le=20)
    hotbar_index: int = Field(default=0, ge=0, le=8)


class OcrStatus(BaseModel):
    position: Optional[Position] = None
    raw_text: Optional[str] = None


class Blackboard(BaseModel):
    """システム全体で共有する状態。"""

    timestamp: float = 0.0
    hud: HudStatus = Field(default_factory=HudStatus)
    ocr: OcrStatus = Field(default_factory=OcrStatus)
    center_block: Optional[str] = None
    stuck_counter: int = 0
    current_task: Optional[str] = None
    last_action_reason: Optional[str] = None

    action_history: Deque[str] = Field(default_factory=lambda: deque(maxlen=32))

    def push_action(self, description: str) -> None:
        self.action_history.append(description)

    def record_reason(self, reason: str) -> None:
        self.last_action_reason = reason
        self.push_action(reason)

    def update_hud(self, hud: HudStatus) -> None:
        self.hud = hud

    def update_ocr(self, ocr: OcrStatus) -> None:
        self.ocr = ocr

    def mark_stuck(self) -> None:
        self.stuck_counter += 1

    def reset_stuck(self) -> None:
        self.stuck_counter = 0


@dataclass
class FrameBundle:
    full: Optional["np.ndarray"]
    downscaled: Optional["np.ndarray"]
    roi2: Optional["np.ndarray"]

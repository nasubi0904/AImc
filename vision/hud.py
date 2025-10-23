"""HUD 情報解析の簡易実装。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from core.state import HudStatus


@dataclass
class HudAnalyzer:
    """テンプレ一致の代替としてダミー計算を提供する。"""

    detector: Optional[Callable[["np.ndarray"], HudStatus]] = None

    def analyze(self, frame) -> HudStatus:
        if self.detector:
            return self.detector(frame)
        # 実装が無い場合は既定値を返す
        return HudStatus(hp=20, hunger=20, hotbar_index=0)

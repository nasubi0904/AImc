"""入力制御ラッパー。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict

try:  # pragma: no cover - 実機環境のみ
    import pydirectinput
except Exception:  # noqa: BLE001
    pydirectinput = None  # type: ignore


class DirectInputDriver:
    """`pydirectinput` を薄く包むドライバ。"""

    def key_down(self, key: str) -> None:
        if not pydirectinput:
            raise RuntimeError("pydirectinput が利用できません")
        pydirectinput.keyDown(key)

    def key_up(self, key: str) -> None:
        if not pydirectinput:
            raise RuntimeError("pydirectinput が利用できません")
        pydirectinput.keyUp(key)

    def move_rel(self, x: int, y: int) -> None:
        if not pydirectinput:
            raise RuntimeError("pydirectinput が利用できません")
        pydirectinput.moveRel(x, y)


@dataclass
class InputController:
    """入力を管理し、安全な停止を保証する。"""

    max_hold_sec: float
    max_click_hz: float
    driver: DirectInputDriver = field(default_factory=DirectInputDriver)

    _held_keys: Dict[str, float] = field(default_factory=dict)
    _last_click: Dict[str, float] = field(default_factory=dict)
    _allowed_keys: set[str] | None = field(default=None, init=False)

    # ------------------------------------------------------------------
    # 許可キー管理
    def set_allowed_keys(self, keys: set[str] | None) -> None:
        """許可されたキーを設定する。``None`` の場合は制限なし。"""

        if keys is None:
            self._allowed_keys = None
        else:
            normalized = {key.strip().lower() for key in keys if key.strip()}
            self._allowed_keys = normalized or set()
        for held in list(self._held_keys.keys()):
            if not self._is_allowed(held):
                self.release(held)

    def allowed_keys(self) -> set[str] | None:
        return None if self._allowed_keys is None else set(self._allowed_keys)

    def _is_allowed(self, key: str) -> bool:
        if self._allowed_keys is None:
            return True
        return key.lower() in self._allowed_keys

    def press(self, key: str) -> None:
        if not self._is_allowed(key):
            return
        now = time.perf_counter()
        if key in self._last_click and now - self._last_click[key] < 1.0 / self.max_click_hz:
            return
        if key in self._held_keys and now - self._held_keys[key] > self.max_hold_sec:
            self.release(key)
        if key not in self._held_keys:
            self.driver.key_down(key)
            self._held_keys[key] = now
        self._last_click[key] = now

    def release(self, key: str) -> None:
        if key in self._held_keys:
            self.driver.key_up(key)
            self._held_keys.pop(key, None)

    def move_mouse(self, x: int, y: int) -> None:
        self.driver.move_rel(x, y)

    def panic_stop(self) -> None:
        """非常停止。全キーを解放する。"""

        for key in list(self._held_keys.keys()):
            self.driver.key_up(key)
        self._held_keys.clear()

    def update(self) -> None:
        """周期処理。長押しし過ぎを防ぐ。"""

        now = time.perf_counter()
        for key, start in list(self._held_keys.items()):
            if now - start > self.max_hold_sec:
                self.driver.key_up(key)
                self._held_keys.pop(key, None)

    def is_holding(self, key: str) -> bool:
        return key in self._held_keys

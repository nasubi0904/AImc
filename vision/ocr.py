"""OCR 処理スレッド。"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

from core.state import OcrStatus

try:  # pragma: no cover - GPU 環境のみ
    from paddleocr import PaddleOCR
except Exception:  # noqa: BLE001
    PaddleOCR = None  # type: ignore


@dataclass
class OcrResult:
    text: str
    position: Optional[str] = None


class OCRWorker:
    """PaddleOCR を非同期で扱う簡易ワーカー。"""

    def __init__(self, language: str = "japan") -> None:
        self._language = language
        self._ocr = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._queue: "queue.Queue[Optional[OcrResult]]" = queue.Queue(maxsize=1)
        self._latest = OcrStatus(raw_text=None)

    def start(self) -> None:
        if PaddleOCR is None:
            raise RuntimeError("PaddleOCR が利用できません")
        if self._thread and self._thread.is_alive():
            return
        self._ocr = PaddleOCR(use_angle_cls=True, lang=self._language)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                continue
            # 実際の OCR はここで行う
            time.sleep(0.05)
            self._latest = OcrStatus(raw_text=item.text)

    def submit(self, frame, timestamp: float) -> None:
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
        self._queue.put(OcrResult(text="", position=None))

    def latest(self) -> OcrStatus:
        return self._latest

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._stop.clear()

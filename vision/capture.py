"""dxcam によるキャプチャ実装。"""
from __future__ import annotations

import time
from dataclasses import dataclass

try:  # pragma: no cover - 実機でのみ利用
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore

try:  # pragma: no cover - 実機でのみ利用
    import dxcam
except Exception:  # noqa: BLE001
    dxcam = None  # type: ignore

from core.config import EnvironmentConfig
from core.state import FrameBundle


@dataclass
class CaptureResult:
    bundle: FrameBundle
    timestamp: float


class DxCameraCapture:
    """dxcam ベースのキャプチャ。"""

    def __init__(self, config: EnvironmentConfig) -> None:
        self._config = config
        self._camera = None
        self._last_capture = 0.0
        self._frame_interval = 1.0 / config.vision.frame_rate

    def _ensure_camera(self) -> None:
        if not dxcam:
            raise RuntimeError("dxcam が利用できません")
        if self._camera is None:
            self._camera = dxcam.create(device_idx=self._config.capture.monitor_id, output_color="BGR")
            self._camera.start(region=self._config.capture.roi)

    def capture(self) -> CaptureResult:
        self._ensure_camera()
        assert self._camera is not None
        now = time.perf_counter()
        if now - self._last_capture < self._frame_interval:
            time.sleep(max(0.0, self._frame_interval - (now - self._last_capture)))
        frame = self._camera.get_latest_frame()
        self._last_capture = time.perf_counter()
        bundle = self._build_bundle(frame)
        return CaptureResult(bundle=bundle, timestamp=self._last_capture)

    def _build_bundle(self, frame) -> FrameBundle:
        if cv2 is None or frame is None:
            return FrameBundle(full=frame, downscaled=None, roi2=None)
        down = cv2.resize(frame, (self._config.capture.downscale.width, self._config.capture.downscale.height))
        roi_size = self._config.capture.roi2_size
        h, w = down.shape[:2]
        cx, cy = w // 2, h // 2
        half = roi_size // 2
        roi2 = down[max(0, cy - half) : min(h, cy + half), max(0, cx - half) : min(w, cx + half)]
        return FrameBundle(full=frame, downscaled=down, roi2=roi2)

    def stop(self) -> None:
        if self._camera:
            self._camera.stop()
            self._camera = None

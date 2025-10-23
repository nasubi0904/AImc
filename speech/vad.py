"""webrtcvad を用いた簡易 VAD。"""
from __future__ import annotations

try:  # pragma: no cover - ランタイム環境依存
    import webrtcvad
except Exception:  # noqa: BLE001
    webrtcvad = None  # type: ignore


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 3) -> None:
        if webrtcvad is None:
            raise RuntimeError("webrtcvad が利用できません")
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._vad.is_speech(frame, sample_rate)

"""faster-whisper を利用した ASR ラッパー。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

try:  # pragma: no cover
    from faster_whisper import WhisperModel
except Exception:  # noqa: BLE001
    WhisperModel = None  # type: ignore


@dataclass
class TranscriptionSegment:
    text: str
    start: float
    end: float


class WhisperTranscriber:
    def __init__(self, model_size: str = "small", compute_type: str = "float16", device: str = "cuda") -> None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper が利用できません")
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio: str, language: str = "ja") -> Iterable[TranscriptionSegment]:
        segments, _ = self._model.transcribe(audio, language=language)
        for segment in segments:
            yield TranscriptionSegment(text=segment.text, start=segment.start, end=segment.end)

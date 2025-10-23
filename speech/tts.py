"""VOICEVOX HTTP API を利用する TTS ラッパー。"""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests


@dataclass
class VoicevoxConfig:
    host: str = "http://127.0.0.1:50021"
    speaker_id: int = 1


class VoicevoxClient:
    def __init__(self, config: VoicevoxConfig) -> None:
        self._config = config

    def synthesize(self, text: str, speed_scale: float = 1.0) -> bytes:
        query_resp = requests.post(
            f"{self._config.host}/audio_query",
            params={"text": text, "speaker": self._config.speaker_id},
        )
        query_resp.raise_for_status()
        query = query_resp.json()
        query["speedScale"] = speed_scale
        synth_resp = requests.post(
            f"{self._config.host}/synthesis",
            params={"speaker": self._config.speaker_id},
            data=json.dumps(query),
            headers={"Content-Type": "application/json"},
        )
        synth_resp.raise_for_status()
        return synth_resp.content

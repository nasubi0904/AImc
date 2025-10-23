"""環境設定 `environmentINFO.yml` の読み込みと検証ロジック。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class PreviewBorderConfig(BaseModel):
    enabled: bool = Field(default=False)
    mode: Literal["off", "line", "corners"] = "off"


class DownscaleConfig(BaseModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class CaptureConfig(BaseModel):
    monitor_id: int = Field(default=0, ge=0)
    roi: Tuple[int, int, int, int]
    preview_border: PreviewBorderConfig = Field(default_factory=PreviewBorderConfig)
    roi2_size: int = Field(default=200, ge=1)
    downscale: DownscaleConfig = Field(default_factory=lambda: DownscaleConfig(width=640, height=360))

    @field_validator("roi")
    @classmethod
    def validate_roi(cls, value: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        x, y, w, h = value
        if min(w, h) <= 0:
            raise ValueError("ROI の幅および高さは正の値である必要があります")
        return value


class AudioAsrConfig(BaseModel):
    device_index: int = 0
    compute_type: str = "float16"


class AudioTtsConfig(BaseModel):
    host: str = "http://127.0.0.1:50021"
    speaker_id: int = Field(default=1, ge=0)


class AudioConfig(BaseModel):
    asr: AudioAsrConfig = Field(default_factory=AudioAsrConfig)
    tts: AudioTtsConfig = Field(default_factory=AudioTtsConfig)


class VisionConfig(BaseModel):
    frame_rate: int = Field(default=20, gt=0)
    ocr_fps: int = Field(default=3, gt=0)


class HotkeyConfig(BaseModel):
    roi_reselect: str = "Ctrl+Alt+R"
    border_toggle: str = "Ctrl+Alt+P"
    panic: str = "Ctrl+Alt+X"


class InputConfig(BaseModel):
    max_hold_sec: float = Field(default=1.2, gt=0)
    max_click_hz: float = Field(default=5.0, gt=0)
    hotkeys: HotkeyConfig = Field(default_factory=HotkeyConfig)


class AgentConfig(BaseModel):
    bt_tick_rate: int = Field(default=5, gt=0)
    default_goal: str = "idle"


class SpeechConfig(BaseModel):
    vad_level: int = Field(default=3, ge=0, le=3)
    asr_language: str = "ja"
    tts_speed: float = Field(default=1.0, gt=0)


class TasksConfig(BaseModel):
    log_dir: str = "logs"
    summary_language: Literal["ja", "en"] = "ja"


class EnvironmentConfig(BaseModel):
    capture: CaptureConfig
    audio: AudioConfig
    vision: VisionConfig
    input: InputConfig
    agent: AgentConfig
    speech: SpeechConfig
    tasks: TasksConfig

    @model_validator(mode="after")
    def ensure_preview_mode(self) -> "EnvironmentConfig":
        mode = self.capture.preview_border.mode
        if mode == "off" and self.capture.preview_border.enabled:
            # ON かつ off は矛盾
            self.capture.preview_border.mode = "line"
        return self

    # ------------------------------------------------------------------
    # 便利メソッド
    def replace_roi(self, monitor_id: int, roi: Tuple[int, int, int, int]) -> None:
        self.capture.monitor_id = monitor_id
        self.capture.roi = roi

    # ------------------------------------------------------------------
    # ファイル入出力
    @classmethod
    def load(cls, path: Path) -> "EnvironmentConfig":
        if not path.exists():
            raise FileNotFoundError(
                "environmentINFO.yml が見つかりません。`environmentINFO.yml.sample` を参考に作成してください。"
            )
        raw: Dict[str, Any]
        with path.open("r", encoding="utf-8") as fp:
            raw = json.load(fp)
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            missing = []
            for err in exc.errors():
                loc = "→".join(str(i) for i in err["loc"])
                missing.append(f"{loc}: {err['msg']}")
            message = "\n".join(missing)
            raise ValueError(f"environmentINFO.yml の検証に失敗しました:\n{message}") from exc

    def save(self, path: Path) -> None:
        payload = self.model_dump(mode="python")
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)


DEFAULT_CONFIG_PATH = Path("environmentINFO.yml")


def load_environment(path: Optional[Path] = None) -> EnvironmentConfig:
    return EnvironmentConfig.load(path or DEFAULT_CONFIG_PATH)


def save_environment(config: EnvironmentConfig, path: Optional[Path] = None) -> None:
    config.save(path or DEFAULT_CONFIG_PATH)

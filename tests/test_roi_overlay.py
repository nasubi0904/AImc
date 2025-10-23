import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.config import EnvironmentConfig

try:
    from ui.roi_overlay import PreviewMode, RoiSelection, create_overlay_app
    _OVERLAY_IMPORT_ERROR: Exception | None = None
    _OVERLAY_SKIP_REASON = ""
except Exception as exc:  # pragma: no cover - グラフィック環境が無い場合
    PreviewMode = RoiSelection = create_overlay_app = None  # type: ignore
    _OVERLAY_IMPORT_ERROR = exc
    _OVERLAY_SKIP_REASON = f"PySide6 の初期化に失敗: {exc}"


@pytest.fixture()
def sample_config_dict():
    return {
        "capture": {
            "monitor_id": 0,
            "roi": [0, 0, 1280, 720],
            "preview_border": {"enabled": False, "mode": "off"},
            "roi2_size": 200,
            "downscale": {"width": 640, "height": 360},
        },
        "audio": {
            "asr": {"device_index": 0, "compute_type": "float16"},
            "tts": {"host": "http://127.0.0.1:50021", "speaker_id": 1},
        },
        "vision": {"frame_rate": 20, "ocr_fps": 3},
        "input": {
            "max_hold_sec": 1.2,
            "max_click_hz": 5,
            "hotkeys": {
                "roi_reselect": "Ctrl+Alt+R",
                "border_toggle": "Ctrl+Alt+P",
                "panic": "Ctrl+Alt+X",
            },
        },
        "agent": {"bt_tick_rate": 5, "default_goal": "idle"},
        "speech": {"vad_level": 3, "asr_language": "ja", "tts_speed": 1.0},
        "tasks": {"log_dir": "logs", "summary_language": "ja"},
    }


def test_environment_config_roundtrip(tmp_path: Path, sample_config_dict):
    config = EnvironmentConfig.model_validate(sample_config_dict)
    config.replace_roi(1, (10, 10, 100, 100))
    target = tmp_path / "environmentINFO.yml"
    config.save(target)

    loaded = EnvironmentConfig.load(target)
    assert loaded.capture.monitor_id == 1
    assert loaded.capture.roi == (10, 10, 100, 100)


@pytest.mark.skipif(_OVERLAY_IMPORT_ERROR is not None, reason=_OVERLAY_SKIP_REASON or "PySide6 の初期化に失敗")
def test_overlay_preview_toggle(sample_config_dict):
    app, overlay = create_overlay_app(
        monitor_id=0,
        roi=(0, 0, 100, 100),
        preview_enabled=False,
        preview_mode="line",
        hotkeys=sample_config_dict["input"]["hotkeys"],
    )
    if not app.screens():
        pytest.skip("スクリーンが取得できない環境ではテストをスキップ")
    overlay.set_preview_mode(PreviewMode.LINE)
    overlay.set_roi(RoiSelection(0, 0, 0, 100, 100))

    overlay.toggle_preview()
    assert overlay.current_roi() is not None
    assert overlay.isVisible() is True

    overlay.toggle_preview()
    assert overlay.isVisible() is False

    app.quit()

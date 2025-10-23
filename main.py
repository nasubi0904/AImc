from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from agent.planner import Planner
from control.input import InputController
from core.config import DEFAULT_CONFIG_PATH, EnvironmentConfig, load_environment, save_environment
from core.state import Blackboard
from tasks.manager import TaskManager, TaskState
from vision.capture import DxCameraCapture
from vision.hud import HudAnalyzer
from vision.ocr import OCRWorker

try:
    from ui.roi_overlay import PreviewMode, RoiSelection, create_overlay_app
except Exception:  # pragma: no cover - GUI 未サポート環境
    PreviewMode = RoiSelection = create_overlay_app = None  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft 自律プレイ最小実装")
    parser.add_argument("--setup", action="store_true", help="ROI セットアップモードを起動")
    parser.add_argument("--live", action="store_true", help="ライブモードを起動")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="設定ファイルパス")
    parser.add_argument("--demo-task", action="store_true", help="デモ用タスクを自動生成")
    return parser.parse_args()


def ensure_config(path: Path) -> EnvironmentConfig:
    return load_environment(path)


def run_setup(config: EnvironmentConfig, path: Path) -> int:
    if create_overlay_app is None:
        print("PySide6 が利用できないため ROI セットアップを実行できません", file=sys.stderr)
        return 1
    app, overlay = create_overlay_app(
        monitor_id=config.capture.monitor_id,
        roi=tuple(config.capture.roi),
        preview_enabled=config.capture.preview_border.enabled,
        preview_mode=config.capture.preview_border.mode,
        hotkeys=config.input.hotkeys.model_dump(),
    )

    def on_commit(selection: RoiSelection) -> None:
        config.replace_roi(selection.monitor_id, selection.as_tuple())
        config.capture.preview_border.enabled = False
        save_environment(config, path)
        print("ROI を保存しました", file=sys.stderr)
        app.quit()

    def on_cancel() -> None:
        print("ROI セットアップをキャンセルしました", file=sys.stderr)
        app.quit()

    overlay.roi_committed.connect(on_commit)
    overlay.roi_canceled.connect(on_cancel)
    overlay.enter_setup_mode()
    app.exec()
    return 0


def run_live(config: EnvironmentConfig, demo_task: bool = False) -> int:
    blackboard = Blackboard()
    inputs = InputController(
        max_hold_sec=config.input.max_hold_sec,
        max_click_hz=config.input.max_click_hz,
    )
    planner = Planner()
    task_manager = TaskManager(Path(config.tasks.log_dir), blackboard)
    planner.bind_task_manager(task_manager)
    tree = planner.plan(config.agent.default_goal, blackboard)
    previous_status = None
    demo_task_id = None
    demo_start_time = None
    if demo_task:
        task = task_manager.create_task("木を1本集める", "デモ開始")
        task_manager.start_task(task.id, "自動デモ開始")
        demo_task_id = task.id
        demo_start_time = time.perf_counter()

    try:
        capture = DxCameraCapture(config)
    except Exception as exc:
        print(f"キャプチャ初期化に失敗しました: {exc}", file=sys.stderr)
        capture = None

    hud = HudAnalyzer()
    ocr = None
    try:
        ocr = OCRWorker(language="japan")
        ocr.start()
    except Exception as exc:  # pragma: no cover - OCR 依存
        print(f"OCR 初期化に失敗しました: {exc}", file=sys.stderr)
        ocr = None

    try:
        while True:
            if capture:
                try:
                    result = capture.capture()
                    blackboard.timestamp = result.timestamp
                except Exception as exc:  # pragma: no cover - 実機依存
                    print(f"キャプチャ取得に失敗: {exc}", file=sys.stderr)
            status = tree.tick(blackboard, inputs)
            if status != previous_status:
                previous_status = status
                blackboard.record_reason(f"BT 状態: {status.name}")
            inputs.update()
            if demo_task_id and demo_start_time and time.perf_counter() - demo_start_time > 1.0:
                task = task_manager.get_task(demo_task_id)
                if task.state == TaskState.RUNNING:
                    task_manager.complete_task(demo_task_id, "デモ動作完了")
                    demo_task_id = None
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("ライブループを終了します", file=sys.stderr)
    finally:
        inputs.panic_stop()
        if capture:
            capture.stop()
        if ocr:
            ocr.stop()
    return 0


def main() -> int:
    args = parse_args()
    if not args.setup and not args.live:
        print("--setup または --live を指定してください", file=sys.stderr)
        return 1

    try:
        config = ensure_config(args.config)
    except FileNotFoundError:
        print("environmentINFO.yml が存在しません。environmentINFO.yml.sample をコピーして編集してください。", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"設定ファイルの検証に失敗しました:\n{exc}", file=sys.stderr)
        return 1

    if args.setup:
        return run_setup(config, args.config)

    if args.live:
        return run_live(config, demo_task=args.demo_task)

    return 0


if __name__ == "__main__":
    sys.exit(main())

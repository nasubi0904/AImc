from __future__ import annotations

import argparse
import signal
import threading
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Set

from agent.planner import Planner
from control.input import InputController
from core.config import DEFAULT_CONFIG_PATH, EnvironmentConfig, load_environment, save_environment
from core.state import Blackboard
from tasks.manager import TaskManager, TaskState
from vision.capture import DxCameraCapture
from vision.hud import HudAnalyzer
from vision.ocr import OCRWorker

try:
    from ui.inspector import InspectorWindow, LiveWorker
    from ui.roi_overlay import PreviewMode, RoiSelection, create_overlay_app
except Exception:  # pragma: no cover - GUI 未サポート環境
    PreviewMode = RoiSelection = create_overlay_app = None  # type: ignore
    InspectorWindow = LiveWorker = None  # type: ignore


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


def run_live(
    config: EnvironmentConfig,
    demo_task: bool = False,
    stop_event: Optional["threading.Event"] = None,
    allowed_keys: Optional[Set[str]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> int:
    blackboard = Blackboard()
    inputs = InputController(
        max_hold_sec=config.input.max_hold_sec,
        max_click_hz=config.input.max_click_hz,
    )
    inputs.set_allowed_keys(allowed_keys)
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

    termination_status = "STOPPED"
    try:
        while True:
            if capture:
                try:
                    result = capture.capture()
                    blackboard.timestamp = result.timestamp
                except Exception as exc:  # pragma: no cover - 実機依存
                    print(f"キャプチャ取得に失敗: {exc}", file=sys.stderr)
            if stop_event and stop_event.is_set():
                blackboard.record_reason("停止要求を受信")
                termination_status = "REQUESTED_STOP"
                break
            status = tree.tick(blackboard, inputs)
            if status != previous_status:
                previous_status = status
                blackboard.record_reason(f"BT 状態: {status.name}")
                if status_callback:
                    status_callback(status.name)
            inputs.update()
            if demo_task_id and demo_start_time and time.perf_counter() - demo_start_time > 1.0:
                task = task_manager.get_task(demo_task_id)
                if task.state == TaskState.RUNNING:
                    task_manager.complete_task(demo_task_id, "デモ動作完了")
                    demo_task_id = None
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("ライブループを終了します", file=sys.stderr)
        termination_status = "INTERRUPTED"
    finally:
        inputs.panic_stop()
        if capture:
            capture.stop()
        if ocr:
            ocr.stop()
        if status_callback:
            status_callback(termination_status)
    return 0


def run_ui(config: EnvironmentConfig, demo_task: bool = False) -> int:
    if create_overlay_app is None or InspectorWindow is None or LiveWorker is None:
        print("PySide6 が利用できないためインスペクタを表示できません", file=sys.stderr)
        return 1

    app, overlay = create_overlay_app(
        monitor_id=config.capture.monitor_id,
        roi=tuple(config.capture.roi),
        preview_enabled=True,
        preview_mode="line",
        hotkeys=config.input.hotkeys.model_dump(),
        preview_color=(255, 64, 64, 230),
    )
    overlay.set_preview_mode(PreviewMode.LINE)
    overlay.set_preview_enabled(True)
    overlay.set_preview_color((255, 64, 64, 230))
    overlay.show()
    overlay.raise_()

    inspector = InspectorWindow(config, overlay)
    roi = overlay.current_roi()
    if roi:
        inspector.move(roi.x + roi.width + 24, roi.y)
    inspector.show()

    from PySide6.QtCore import QThread, QTimer

    worker_thread: Optional[QThread] = None
    worker: Optional[LiveWorker] = None

    def on_worker_finished(exit_code: int) -> None:
        nonlocal worker_thread, worker
        inspector.set_running(False)
        if exit_code != 0:
            inspector.update_status(f"エラー終了 (code={exit_code})")
        if worker_thread:
            worker_thread.quit()
            worker_thread.wait()
            worker_thread = None
        if worker:
            worker = None

    def start_session(allowed: Optional[Set[str]]) -> None:
        nonlocal worker_thread, worker
        if worker_thread is not None:
            return
        inspector.set_running(True)
        worker_thread = QThread()
        worker = LiveWorker(run_live, config, demo_task=demo_task)
        worker.set_allowed_keys(allowed)
        worker.moveToThread(worker_thread)
        worker.status_changed.connect(inspector.update_status)
        worker.error_occurred.connect(inspector.show_error)
        worker.finished.connect(on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker_thread.finished.connect(worker_thread.deleteLater)
        worker_thread.started.connect(worker.run)
        worker_thread.start()

    def stop_session() -> None:
        if worker:
            worker.request_stop()

    inspector.start_requested.connect(start_session)
    inspector.stop_requested.connect(stop_session)

    def handle_sigint(_signum, _frame) -> None:
        if worker:
            worker.request_stop()
        else:
            app.quit()

    signal.signal(signal.SIGINT, handle_sigint)

    pulse = QTimer()
    pulse.setInterval(150)
    pulse.timeout.connect(lambda: None)
    pulse.start()

    app.exec()
    if worker_thread:
        worker_thread.quit()
        worker_thread.wait()
    return 0


def main() -> int:
    args = parse_args()

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

    return run_ui(config, demo_task=args.demo_task)


if __name__ == "__main__":
    sys.exit(main())

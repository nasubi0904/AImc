"""インスペクタ UI とライブ実行ワーカー。"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Sequence, Set

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import EnvironmentConfig
from ui.roi_overlay import PreviewMode, RoiOverlayController


class LiveWorker(QObject):
    """バックグラウンドで `run_live` を実行するワーカー。"""

    finished = Signal(int)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        runner: Callable[[EnvironmentConfig, bool, Optional[threading.Event], Optional[Set[str]], Optional[Callable[[str], None]]], int],
        config: EnvironmentConfig,
        demo_task: bool = False,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._config = config
        self._demo_task = demo_task
        self._stop_event = threading.Event()
        self._allowed_keys: Optional[Set[str]] = None

    def set_allowed_keys(self, keys: Optional[Set[str]]) -> None:
        self._allowed_keys = keys

    def request_stop(self) -> None:
        self._stop_event.set()

    @Slot()
    def run(self) -> None:
        exit_code = 1
        try:
            exit_code = self._runner(
                self._config,
                demo_task=self._demo_task,
                stop_event=self._stop_event,
                allowed_keys=self._allowed_keys,
                status_callback=self.status_changed.emit,
            )
        except Exception as exc:  # pragma: no cover - 実行環境依存
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit(exit_code)


class InspectorWindow(QWidget):
    """赤枠と AI 制御を管理するインスペクタ。"""

    start_requested = Signal(object)
    stop_requested = Signal()

    def __init__(self, _config: EnvironmentConfig, overlay: RoiOverlayController) -> None:
        super().__init__()
        self._overlay = overlay
        self._running = False
        self.setWindowTitle("AImc インスペクタ")
        self._allowed_keys_input = QLineEdit()
        self._allowed_keys_input.setPlaceholderText("例: w, a, s, d, space, shift")
        self._allowed_keys_input.setText("w, a, s, d, space, shift")

        self._status_label = QLabel("停止中")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._preview_checkbox = QCheckBox("赤枠を表示")
        self._preview_checkbox.setChecked(self._overlay.is_preview_enabled())
        self._preview_checkbox.toggled.connect(self._overlay.set_preview_enabled)

        self._preview_mode_combo = QComboBox()
        self._preview_mode_combo.addItems(["off", "line", "corners"])
        self._preview_mode_combo.setCurrentText(self._overlay.preview_mode().value)
        self._preview_mode_combo.currentTextChanged.connect(self._on_preview_mode_changed)

        self._roi_label = QLabel(self._format_roi(self._overlay.current_roi()))
        self._roi_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._start_button = QPushButton("スタート")
        self._start_button.clicked.connect(self._emit_start)

        self._stop_button = QPushButton("停止")
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self.stop_requested.emit)

        settings_group = QGroupBox("キャプチャ設定")
        settings_layout = QFormLayout()
        settings_layout.addRow("ROI", self._roi_label)
        settings_layout.addRow("プレビュー", self._preview_checkbox)
        settings_layout.addRow("描画モード", self._preview_mode_combo)
        settings_group.setLayout(settings_layout)

        input_group = QGroupBox("入力制御")
        input_layout = QFormLayout()
        input_layout.addRow("許可キー", self._allowed_keys_input)
        input_group.setLayout(input_layout)

        status_group = QGroupBox("ステータス")
        status_layout = QVBoxLayout()
        status_layout.addWidget(self._status_label)
        status_group.setLayout(status_layout)

        button_row = QHBoxLayout()
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._stop_button)

        root_layout = QVBoxLayout(self)
        root_layout.addWidget(settings_group)
        root_layout.addWidget(input_group)
        root_layout.addWidget(status_group)
        root_layout.addLayout(button_row)

        overlay.roi_committed.connect(self._on_roi_committed)
        overlay.preview_toggled.connect(self._on_preview_toggled)
        overlay.panic_requested.connect(self.stop_requested.emit)

        self.setFixedWidth(320)

    # ------------------------------------------------------------------
    # 外部インターフェース
    def set_running(self, running: bool) -> None:
        self._running = running
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        if running:
            self.update_status("AI 起動中…")

    def update_status(self, status: str) -> None:
        translations = {
            "STOPPED": "停止中",
            "REQUESTED_STOP": "停止処理中…",
            "INTERRUPTED": "ユーザー中断",
            "RUNNING": "実行中",
            "SUCCESS": "成功",
            "FAILURE": "失敗",
        }
        self._status_label.setText(translations.get(status, status))

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "エラー", message)

    def allowed_keys(self) -> Optional[Set[str]]:
        tokens = self._split_keys(self._allowed_keys_input.text())
        if not tokens:
            return None
        return {token.lower() for token in tokens}

    # ------------------------------------------------------------------
    # Qt イベント
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: D401 - Qt 規約
        if self._running:
            self.stop_requested.emit()
            event.ignore()
            QMessageBox.information(self, "停止待ち", "AI 実行を停止してからウィンドウを閉じてください。")
        else:
            super().closeEvent(event)

    # ------------------------------------------------------------------
    # 内部処理
    def _emit_start(self) -> None:
        if self._running:
            return
        self.start_requested.emit(self.allowed_keys())

    def _on_preview_mode_changed(self, text: str) -> None:
        mode = PreviewMode(text if text in PreviewMode._value2member_map_ else PreviewMode.OFF.value)
        self._overlay.set_preview_mode(mode)

    def _on_roi_committed(self, selection) -> None:
        self._roi_label.setText(self._format_roi(selection))

    def _on_preview_toggled(self, enabled: bool, _mode: str) -> None:
        if self._preview_checkbox.isChecked() != enabled:
            self._preview_checkbox.blockSignals(True)
            self._preview_checkbox.setChecked(enabled)
            self._preview_checkbox.blockSignals(False)

    @staticmethod
    def _split_keys(text: str) -> Sequence[str]:
        cleaned = text.replace("、", ",").replace(" ", ",")
        parts = [token.strip() for token in cleaned.split(",")]
        return [token for token in parts if token]

    @staticmethod
    def _format_roi(roi) -> str:
        if not roi:
            return "未設定"
        return f"Monitor {roi.monitor_id}: x={roi.x}, y={roi.y}, w={roi.width}, h={roi.height}"

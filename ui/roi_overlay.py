"""ROI オーバーレイ UI の実装。

PySide6 を用いてキャプチャ範囲の選択およびプレビューを提供する。UI ロジックは
テスト容易性を意識して分離し、環境設定の保存・復元は別コンポーネントに委譲する。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import QApplication, QLabel, QRubberBand, QShortcut, QVBoxLayout, QWidget


class PreviewMode(str, Enum):
    """ROI プレビューの描画モード。"""

    OFF = "off"
    LINE = "line"
    CORNERS = "corners"


@dataclass
class RoiSelection:
    """ROI 情報を保持するデータクラス。"""

    monitor_id: int
    x: int
    y: int
    width: int
    height: int

    def to_rect(self) -> QRect:
        return QRect(self.x, self.y, self.width, self.height)

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


class RoiOverlayController(QWidget):
    """ROI オーバーレイウィンドウ。

    システム全体から利用しやすいように QWidget を直接継承し、ホットキー操作や
    選択結果を Qt のシグナルで公開する。
    """

    roi_committed = Signal(object)
    roi_canceled = Signal()
    panic_requested = Signal()
    preview_toggled = Signal(bool, str)

    def __init__(
        self,
        monitor_id: int,
        roi: Optional[RoiSelection],
        preview_enabled: bool,
        preview_mode: PreviewMode,
        hotkeys: dict,
        parent: Optional[QWidget] = None,
        preview_color: Tuple[int, int, int, int] = (0, 200, 255, 230),
    ) -> None:
        super().__init__(parent)
        self._monitor_id = monitor_id
        self._current_roi: Optional[RoiSelection] = roi
        self._preview_enabled = preview_enabled
        self._preview_mode = preview_mode
        self._hotkeys = hotkeys
        self._preview_pen_color = QColor(*preview_color)

        self._setup_mode = False
        self._rubber_band: Optional[QRubberBand] = None
        self._origin: Optional[QPoint] = None

        self._hud = QLabel(self)
        self._hud.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 160);"
            "border-radius: 6px; padding: 6px;"
        )
        self._hud.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._hud, alignment=Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(12, 12, 12, 12)

        self._apply_screen_geometry()
        self._apply_window_flags()
        self._install_hotkeys()
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # 初期化関連
    def _apply_window_flags(self) -> None:
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._update_mouse_transparency()

    def _apply_screen_geometry(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            raise RuntimeError("モニタ情報を取得できませんでした")
        if self._monitor_id >= len(screens) or self._monitor_id < 0:
            self._monitor_id = 0
        screen = screens[self._monitor_id]
        self.setGeometry(screen.geometry())

    def _install_hotkeys(self) -> None:
        QShortcut(QKeySequence(self._hotkeys.get("roi_reselect", "Ctrl+Alt+R")), self, activated=self.enter_setup_mode)
        QShortcut(
            QKeySequence(self._hotkeys.get("border_toggle", "Ctrl+Alt+P")),
            self,
            activated=self.toggle_preview,
        )
        QShortcut(
            QKeySequence(self._hotkeys.get("panic", "Ctrl+Alt+X")),
            self,
            activated=self._request_panic,
        )

    # ------------------------------------------------------------------
    # 公開 API
    def enter_setup_mode(self) -> None:
        """ROI 再選択モードを開始。"""

        self._setup_mode = True
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubber_band.hide()
        self._origin = None
        self._hud.setVisible(True)
        self.show()
        self.raise_()
        self._update_mouse_transparency()

    def leave_setup_mode(self) -> None:
        self._setup_mode = False
        if self._rubber_band:
            self._rubber_band.hide()
            self._rubber_band.deleteLater()
            self._rubber_band = None
        self._origin = None
        self._hud.setVisible(False)
        self._update_mouse_transparency()
        if not self._preview_enabled:
            self.hide()

    def set_roi(self, roi: RoiSelection) -> None:
        self._current_roi = roi
        if not self._setup_mode and not self._preview_enabled:
            self.hide()
        self.update()

    def current_roi(self) -> Optional[RoiSelection]:
        return self._current_roi

    def toggle_preview(self) -> None:
        self.set_preview_enabled(not self._preview_enabled)

    def set_preview_enabled(self, enabled: bool) -> None:
        self._preview_enabled = enabled
        if self._preview_enabled:
            if not self.isVisible():
                self.show()
        else:
            if not self._setup_mode:
                self.hide()
        self.preview_toggled.emit(self._preview_enabled, self._preview_mode.value)
        self.update()

    def set_preview_mode(self, mode: PreviewMode) -> None:
        self._preview_mode = mode
        self.update()

    def set_preview_color(self, color: Tuple[int, int, int, int]) -> None:
        self._preview_pen_color = QColor(*color)
        self.update()

    def is_preview_enabled(self) -> bool:
        return self._preview_enabled

    def preview_mode(self) -> PreviewMode:
        return self._preview_mode

    # ------------------------------------------------------------------
    # 内部処理
    def _update_mouse_transparency(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not self._setup_mode)

    def _commit_roi(self) -> None:
        if not self._current_roi:
            return
        self.roi_committed.emit(self._current_roi)
        self.leave_setup_mode()

    def _cancel_roi(self) -> None:
        self.roi_canceled.emit()
        self.leave_setup_mode()

    def _request_panic(self) -> None:
        self.panic_requested.emit()

    # ------------------------------------------------------------------
    # イベント処理
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._setup_mode or event.button() != Qt.MouseButton.LeftButton:
            return
        self._origin = event.position().toPoint()
        if self._rubber_band:
            self._rubber_band.setGeometry(QRect(self._origin, QSize(1, 1)))
            self._rubber_band.show()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not self._setup_mode or not self._origin or not self._rubber_band:
            return
        current = event.position().toPoint()
        rect = QRect(self._origin, current).normalized()
        self._rubber_band.setGeometry(rect)
        self._update_hud(rect)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if not self._setup_mode or event.button() != Qt.MouseButton.LeftButton:
            return
        if not self._rubber_band or not self._origin:
            return
        rect = self._rubber_band.geometry()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        top_left = self.mapToGlobal(rect.topLeft())
        self._current_roi = RoiSelection(
            monitor_id=self._monitor_id,
            x=top_left.x(),
            y=top_left.y(),
            width=rect.width(),
            height=rect.height(),
        )
        self._update_hud(rect)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if not self._setup_mode:
            return
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self._current_roi:
                self._commit_roi()
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_roi()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if not self._preview_enabled or not self._current_roi:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._preview_pen_color, 2)
        painter.setPen(pen)
        roi_rect = self._map_roi_to_widget(self._current_roi)
        if self._preview_mode == PreviewMode.LINE:
            painter.drawRect(roi_rect)
        elif self._preview_mode == PreviewMode.CORNERS:
            self._draw_corners(painter, roi_rect)
        painter.end()

    # ------------------------------------------------------------------
    # ユーティリティ
    def _map_roi_to_widget(self, roi: RoiSelection) -> QRect:
        widget_top_left = self.mapFromGlobal(QPoint(roi.x, roi.y))
        return QRect(widget_top_left, roi.to_rect().size())

    def _draw_corners(self, painter: QPainter, rect: QRect) -> None:
        corner = 24
        # 上
        painter.drawLine(rect.topLeft(), rect.topLeft() + QPoint(corner, 0))
        painter.drawLine(rect.topLeft(), rect.topLeft() + QPoint(0, corner))
        painter.drawLine(rect.topRight(), rect.topRight() + QPoint(-corner, 0))
        painter.drawLine(rect.topRight(), rect.topRight() + QPoint(0, corner))
        # 下
        painter.drawLine(rect.bottomLeft(), rect.bottomLeft() + QPoint(corner, 0))
        painter.drawLine(rect.bottomLeft(), rect.bottomLeft() + QPoint(0, -corner))
        painter.drawLine(rect.bottomRight(), rect.bottomRight() + QPoint(-corner, 0))
        painter.drawLine(rect.bottomRight(), rect.bottomRight() + QPoint(0, -corner))

    def _update_hud(self, rect: QRect) -> None:
        if not rect.isValid():
            return
        global_rect = QRect(self.mapToGlobal(rect.topLeft()), rect.size())
        self._hud.setText(
            f"Monitor {self._monitor_id}\n"
            f"x={global_rect.x()}, y={global_rect.y()}\n"
            f"w={global_rect.width()}, h={global_rect.height()}"
        )


def create_overlay_app(
    monitor_id: int,
    roi: Optional[Tuple[int, int, int, int]],
    preview_enabled: bool,
    preview_mode: str,
    hotkeys: dict,
    preview_color: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[QApplication, RoiOverlayController]:
    """テストやスクリプトから簡単に呼び出すためのヘルパー関数。"""

    app = QApplication.instance() or QApplication([])
    selection = None
    if roi:
        selection = RoiSelection(monitor_id, *roi)
    overlay = RoiOverlayController(
        monitor_id=monitor_id,
        roi=selection,
        preview_enabled=preview_enabled,
        preview_mode=PreviewMode(preview_mode if preview_mode in PreviewMode._value2member_map_ else "off"),
        hotkeys=hotkeys,
        preview_color=preview_color or (0, 200, 255, 230),
    )
    return app, overlay

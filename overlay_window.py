from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from config import OverlayConfig

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

_user32 = ctypes.windll.user32
_user32.GetWindowLongW.restype = ctypes.c_long
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongW.restype = ctypes.c_long
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

_CORNER_ZONES = {
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
}

MIN_WIDTH = 120
MIN_HEIGHT = 80


def set_click_through(hwnd: int, enabled: bool) -> None:
    style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enabled:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


class OverlayWindow(QWidget):
    geometry_changed = Signal()

    def __init__(self, config: OverlayConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self._cfg = config
        self._hwnd: int | None = None
        self._click_through_active = False
        self._drag_mode: str | None = None
        self._drag_start_global = QPoint()
        self._drag_start_geom = QRect()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMouseTracking(True)
        self.resize(config.default_width, config.default_height)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)
        self._poll_timer.timeout.connect(self._poll_cursor)

    # -- lifecycle -----------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._hwnd = int(self.winId())
        self._click_through_active = False
        set_click_through(self._hwnd, False)
        self._poll_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._poll_timer.stop()

    # -- painting --------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        thickness = self._cfg.border_thickness
        pen = QPen(QColor(255, 60, 60), thickness)
        painter.setPen(pen)
        half = thickness // 2
        painter.drawRect(self.rect().adjusted(half, half, -half - 1, -half - 1))

    # -- hit testing -------------------------------------------------------

    def _hit_zone(self, pos: QPoint) -> str:
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        if x < 0 or y < 0 or x >= w or y >= h:
            return "outside"
        corner = self._cfg.corner_size
        border = self._cfg.border_thickness
        near_left = x < corner
        near_right = x >= w - corner
        near_top = y < corner
        near_bottom = y >= h - corner
        if near_top and near_left:
            return "nw"
        if near_top and near_right:
            return "ne"
        if near_bottom and near_left:
            return "sw"
        if near_bottom and near_right:
            return "se"
        if x < border or x >= w - border or y < border or y >= h - border:
            return "move"
        return "interior"

    # -- click-through polling -------------------------------------------

    def _poll_cursor(self):
        if self._drag_mode is not None or self._hwnd is None:
            return
        local = self.mapFromGlobal(QCursor.pos())
        zone = self._hit_zone(local)
        want_click_through = zone in ("interior", "outside")
        if want_click_through != self._click_through_active:
            set_click_through(self._hwnd, want_click_through)
            self._click_through_active = want_click_through
        self._update_cursor(zone)

    def _update_cursor(self, zone: str):
        if zone in _CORNER_ZONES:
            self.setCursor(_CORNER_ZONES[zone])
        elif zone == "move":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()

    # -- mouse handling (only fires when non-click-through, i.e. on border) -

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        zone = self._hit_zone(event.position().toPoint())
        if zone in ("move", "nw", "ne", "sw", "se"):
            self._drag_mode = zone
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_geom = QRect(self.geometry())

    def mouseMoveEvent(self, event):
        if self._drag_mode is None:
            self._update_cursor(self._hit_zone(event.position().toPoint()))
            return
        delta = event.globalPosition().toPoint() - self._drag_start_global
        start = self._drag_start_geom
        geom = QRect(start)
        if self._drag_mode == "move":
            geom.moveTopLeft(start.topLeft() + delta)
        else:
            left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
            if "n" in self._drag_mode:
                top = min(start.top() + delta.y(), bottom - MIN_HEIGHT)
            if "s" in self._drag_mode:
                bottom = max(start.bottom() + delta.y(), top + MIN_HEIGHT)
            if "w" in self._drag_mode:
                left = min(start.left() + delta.x(), right - MIN_WIDTH)
            if "e" in self._drag_mode:
                right = max(start.right() + delta.x(), left + MIN_WIDTH)
            geom.setCoords(left, top, right, bottom)
        self.setGeometry(geom)
        self.geometry_changed.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_mode = None

    def moveEvent(self, event):
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.geometry_changed.emit()

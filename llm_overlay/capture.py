from __future__ import annotations

from PySide6.QtCore import QBuffer, QIODevice, QRect
from PySide6.QtGui import QGuiApplication, QPixmap


def grab_region(global_rect: QRect) -> QPixmap:
    """Capture the screen pixels under global_rect (in virtual-desktop coordinates)."""
    screen = QGuiApplication.screenAt(global_rect.center()) or QGuiApplication.primaryScreen()
    local = global_rect.translated(-screen.geometry().topLeft())
    return screen.grabWindow(
        0, local.x(), local.y(), local.width(), local.height()
    )


def pixmap_to_png_bytes(pixmap: QPixmap) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    return bytes(buf.data())

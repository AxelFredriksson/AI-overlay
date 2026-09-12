from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from capture import grab_region
from config import Config, has_api_key, load_config, save_config
from history import HistoryStore
from hotkey import GlobalHotkey
from llm.gemini_client import GeminiBackend, LLMError
from overlay_toolbar import OverlayToolbar
from overlay_window import OverlayWindow
from panel_window import PanelWindow
from settings_dialog import SettingsDialog


class Controller:
    def __init__(self, app: QApplication, config: Config):
        self.app = app
        self.config = config
        self.history = HistoryStore(config.history_path)
        self.backend = self._build_backend(config)
        self.visible = False

        self.overlay = OverlayWindow(config.overlay)
        self.toolbar = OverlayToolbar()
        self.panel = PanelWindow(config, self.backend, self.history)

        self.overlay.geometry_changed.connect(self._sync_toolbar)
        self.toolbar.ask_clicked.connect(self._on_ask)
        self.toolbar.close_clicked.connect(self.hide_overlay)

        self._build_tray_icon()

    @staticmethod
    def _build_backend(config: Config) -> GeminiBackend | None:
        if not has_api_key(config):
            return None
        try:
            return GeminiBackend(config.gemini_api_key, config.model)
        except LLMError as exc:
            print(f"Could not initialize Gemini backend: {exc}")
            return None

    def _build_tray_icon(self) -> None:
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(255, 60, 60))
        self.tray = QSystemTrayIcon(QIcon(pixmap), self.app)
        self.tray.setToolTip("LLM Overlay")

        self.tray_menu = QMenu()
        toggle_action = QAction("Visa/Dölj overlay", self.tray_menu)
        toggle_action.triggered.connect(self.toggle_overlay)
        self.tray_menu.addAction(toggle_action)

        quit_action = QAction("Avsluta", self.tray_menu)
        quit_action.triggered.connect(self.app.quit)
        self.tray_menu.addAction(quit_action)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def _sync_toolbar(self) -> None:
        self.toolbar.follow(self.overlay.geometry())

    def show_overlay(self) -> None:
        self.overlay.show()
        self.toolbar.show()
        self._sync_toolbar()
        self.visible = True

    def hide_overlay(self) -> None:
        self.overlay.hide()
        self.toolbar.hide()
        self.panel.hide()
        self.visible = False

    def toggle_overlay(self) -> None:
        self.hide_overlay() if self.visible else self.show_overlay()

    def _on_ask(self) -> None:
        box_rect = self.overlay.geometry()
        self.overlay.hide()
        self.toolbar.hide()
        pixmap = grab_region(box_rect)
        self.overlay.show()
        self.toolbar.show()
        self._sync_toolbar()
        self.panel.start_capture(pixmap)
        self.panel.position_near(box_rect)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config()
    save_config(config)  # normalize settings.json / migrate a legacy key into .env
    if not has_api_key(config):
        dialog = SettingsDialog(config)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            sys.exit(0)
        config = dialog.result_config()
        save_config(config)

    controller = Controller(app, config)

    hotkey = GlobalHotkey(config.hotkey)
    app.installNativeEventFilter(hotkey)
    if not hotkey.register():
        print(f"Warning: could not register hotkey '{config.hotkey}' (already in use?)")
    hotkey.triggered.connect(controller.toggle_overlay)

    controller.show_overlay()

    exit_code = app.exec()
    hotkey.unregister()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

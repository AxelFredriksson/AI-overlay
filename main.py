from __future__ import annotations

import sys

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
from theme import ThemeManager


class Controller:
    def __init__(self, app: QApplication, config: Config):
        self.app = app
        self.config = config
        self.history = HistoryStore(config.history_path)
        self.backend = self._build_backend(config)
        self.visible = False
        self.hotkey: GlobalHotkey | None = None
        self.theme = ThemeManager(config.theme)

        self.overlay = OverlayWindow(config.overlay)
        self.toolbar = OverlayToolbar()
        self.panel = PanelWindow(config, self.backend, self.history, self.theme)

        self.overlay.geometry_changed.connect(self._sync_toolbar)
        self.toolbar.ask_clicked.connect(self._on_ask)
        self.toolbar.chat_clicked.connect(self._on_chat)
        self.toolbar.close_clicked.connect(self.hide_overlay)
        self.toolbar.settings_clicked.connect(self.open_settings)
        self.panel.open_settings_requested.connect(self.open_settings)
        self.theme.changed.connect(self._apply_theme)

        self._apply_theme()
        self._build_tray_icon()
        self._register_hotkey()

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        self.overlay.apply_theme(palette)
        self.toolbar.apply_theme(palette)

    @staticmethod
    def _build_backend(config: Config) -> GeminiBackend | None:
        if not has_api_key(config):
            return None
        try:
            return GeminiBackend(config.gemini_api_key, config.model)
        except LLMError as exc:
            print(f"Could not initialize Gemini backend: {exc}")
            return None

    def _register_hotkey(self) -> None:
        if self.hotkey is not None:
            self.hotkey.unregister()
            self.app.removeNativeEventFilter(self.hotkey)
        self.hotkey = GlobalHotkey(self.config.hotkey)
        self.app.installNativeEventFilter(self.hotkey)
        if not self.hotkey.register():
            print(f"Warning: could not register hotkey '{self.config.hotkey}' (already in use?)")
        self.hotkey.triggered.connect(self.toggle_overlay)

    def _build_tray_icon(self) -> None:
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(255, 60, 60))
        self.tray = QSystemTrayIcon(QIcon(pixmap), self.app)
        self.tray.setToolTip("LLM Overlay")

        self.tray_menu = QMenu()
        toggle_action = QAction("Visa/Dölj overlay", self.tray_menu)
        toggle_action.triggered.connect(self.toggle_overlay)
        self.tray_menu.addAction(toggle_action)

        settings_action = QAction("Inställningar", self.tray_menu)
        settings_action.triggered.connect(self.open_settings)
        self.tray_menu.addAction(settings_action)

        quit_action = QAction("Avsluta", self.tray_menu)
        quit_action.triggered.connect(self.app.quit)
        self.tray_menu.addAction(quit_action)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self.theme)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            save_config(self.config)
            self.backend = self._build_backend(self.config)
            self.panel.set_backend(self.backend)
            self._register_hotkey()
        # Frame colour/width and the theme are edited live, so repaint either way.
        self._apply_theme()

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
        self.toolbar.set_busy(True)
        self.app.processEvents()
        box_rect = self.overlay.geometry()
        self.overlay.hide()
        self.toolbar.hide()
        pixmap = grab_region(box_rect)
        self.overlay.show()
        self.toolbar.show()
        self.toolbar.set_busy(False)
        self._sync_toolbar()
        self.panel.start_capture(pixmap)
        self.panel.position_near(box_rect)
        if self.config.auto_send:
            self.panel.submit_auto()

    def _on_chat(self) -> None:
        self.panel.start_chat()
        self.panel.position_near(self.overlay.geometry())


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    config = load_config()
    save_config(config)  # normalize settings.json / migrate a legacy key into .env
    if not has_api_key(config):
        dialog = SettingsDialog(config, ThemeManager(config.theme))
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            sys.exit(0)
        config = dialog.result_config()
        save_config(config)

    controller = Controller(app, config)
    controller.show_overlay()

    exit_code = app.exec()
    if controller.hotkey is not None:
        controller.hotkey.unregister()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

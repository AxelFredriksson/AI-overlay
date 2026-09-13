from __future__ import annotations

import json

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout

from llm_overlay.config import Config
from llm_overlay.hotkey import HotkeyParseError, parse_hotkey
from llm_overlay.theme import MODES, ThemeManager, apply_titlebar_theme, css_variables
from llm_overlay.ui.webview import build_web_view

MODEL_CHOICES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]

DETAIL_LEVEL_LABELS = {
    "kort": "Kort",
    "medel": "Medel",
    "detaljerad": "Detaljerad",
}

THINKING_LEVEL_LABELS = {
    "dynamic": "Standard (dynamisk)",
    "low": "Låg",
    "medium": "Medel",
    "high": "Hög",
}

THEME_MODE_LABELS = {"system": "System", "light": "Ljust", "dark": "Mörkt"}

COLOR_PRESETS = [
    {"value": "", "label": "Följ tema"},
    {"value": "#4C6B5A", "label": "Salvia"},
    {"value": "#2C2823", "label": "Bläck"},
    {"value": "#F4F1EA", "label": "Papper"},
    {"value": "#C0392B", "label": "Röd"},
    {"value": "#D97706", "label": "Orange"},
    {"value": "#2563EB", "label": "Blå"},
    {"value": "#DB2777", "label": "Magenta"},
]


class SettingsBridge(QObject):
    stateChanged = Signal(str)
    themeChanged = Signal(str)
    saveFailed = Signal(str)
    saved = Signal()
    cancelled = Signal()
    quitRequested = Signal()

    def __init__(self, config: Config, theme_manager: ThemeManager | None, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config
        self._theme = theme_manager
        # Theme changes are previewed live; the original is restored unless the user saves.
        self._original_theme_mode = theme_manager.mode if theme_manager else config.theme

    def _state(self) -> dict:
        config = self._config
        palette_vars = css_variables(self._theme.palette) if self._theme else ""
        return {
            "theme": {"vars": palette_vars},
            "config": {
                "apiKey": config.gemini_api_key,
                "hasKey": bool(config.gemini_api_key.strip()),
                "model": config.model,
                "models": MODEL_CHOICES,
                "hotkey": config.hotkey,
                "autoSend": config.auto_send,
                "autoSendQuestion": config.auto_send_question,
                "detailLevel": config.detail_level,
                "detailLevels": list(DETAIL_LEVEL_LABELS.items()),
                "thinkingLevel": config.thinking_level,
                "thinkingLevels": list(THINKING_LEVEL_LABELS.items()),
                "saveHistory": config.save_history,
                # The live manager, not the config: a previewed theme must stay selected, otherwise
                # the page snaps the choice back and saves the old one.
                "themeMode": self._theme.mode if self._theme else config.theme,
                "themeModes": list(THEME_MODE_LABELS.items()),
                "historyPath": str(config.history_path),
                "overlay": {
                    "width": config.overlay.default_width,
                    "height": config.overlay.default_height,
                    "lineWidth": config.overlay.line_width,
                    "grab": config.overlay.border_thickness,
                    "corner": config.overlay.corner_size,
                    "color": config.overlay.color,
                    "colorPresets": COLOR_PRESETS,
                },
            },
        }

    @Slot()
    def ready(self) -> None:
        self.stateChanged.emit(json.dumps(self._state()))

    @Slot(str)
    def previewTheme(self, mode: str) -> None:  # noqa: N802 - JS-facing name
        # Only the palette goes back to the page: a full state push would re-render the form and
        # discard whatever the user has typed but not saved yet.
        if self._theme is not None:
            self._theme.set_mode(mode)
            self.themeChanged.emit(css_variables(self._theme.palette))

    @Slot()
    def openHistoryFolder(self) -> None:  # noqa: N802 - JS-facing name
        self._config.history_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._config.history_path)))

    @Slot()
    def cancel(self) -> None:
        self.cancelled.emit()

    @Slot()
    def quitApp(self) -> None:  # noqa: N802 - JS-facing name
        self.quitRequested.emit()

    @Slot(str)
    def save(self, payload: str) -> None:
        data = json.loads(payload)
        api_key = data["apiKey"].strip()
        hotkey = data["hotkey"].strip().lower()
        if not api_key:
            self.saveFailed.emit("API-nyckel krävs.")
            return
        try:
            parse_hotkey(hotkey)
        except HotkeyParseError as exc:
            self.saveFailed.emit(str(exc))
            return

        config = self._config
        config.gemini_api_key = api_key
        config.model = data["model"].strip() or "gemini-3.6-flash"
        config.hotkey = hotkey
        config.auto_send = bool(data["autoSend"])
        config.auto_send_question = data["autoSendQuestion"].strip() or config.auto_send_question
        config.detail_level = data["detailLevel"]
        config.thinking_level = data["thinkingLevel"]
        config.save_history = bool(data["saveHistory"])
        config.theme = data["themeMode"]
        overlay = data["overlay"]
        frame_color = overlay["color"].strip()
        if frame_color and not QColor(frame_color).isValid():
            self.saveFailed.emit(f"Ogiltig ramfärg: {frame_color}")
            return
        config.overlay.color = frame_color
        config.overlay.default_width = int(overlay["width"])
        config.overlay.default_height = int(overlay["height"])
        config.overlay.line_width = int(overlay["lineWidth"])
        config.overlay.border_thickness = int(overlay["grab"])
        config.overlay.corner_size = int(overlay["corner"])

        if self._theme is not None:
            self._theme.set_mode(config.theme)
        self.saved.emit()

    def restore_theme(self) -> None:
        """Undoes the live preview when the dialog closes without saving."""
        if self._theme is not None:
            self._theme.set_mode(self._original_theme_mode)


class SettingsDialog(QDialog):
    def __init__(self, config: Config, theme_manager: ThemeManager | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Overlay – Inställningar")
        self.setModal(True)
        self.resize(780, 520)
        self._config = config
        self._theme = theme_manager

        self.bridge = SettingsBridge(config, theme_manager, self)
        self.bridge.saved.connect(self.accept)
        self.bridge.cancelled.connect(self.reject)
        self.bridge.quitRequested.connect(self._on_quit)

        self.view = build_web_view("settings.html", self.bridge, transparent=False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._theme is not None:
            apply_titlebar_theme(self, self._theme.resolved_mode() == "dark")

    def reject(self) -> None:  # noqa: N802 - Qt override
        self.bridge.restore_theme()
        super().reject()

    def _on_quit(self) -> None:
        self.reject()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def result_config(self) -> Config:
        return self._config

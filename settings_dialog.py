from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from config import Config
from hotkey import HotkeyParseError, parse_hotkey

MODEL_CHOICES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LLM Overlay - Inställningar")
        self.setModal(True)
        self._config = config

        self.api_key_input = QLineEdit(config.gemini_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Din Gemini API-nyckel")

        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.addItems(MODEL_CHOICES)
        self.model_input.setCurrentText(config.model)

        self.hotkey_input = QLineEdit(config.hotkey)
        self.hotkey_input.setPlaceholderText("t.ex. ctrl+shift+o")

        form = QFormLayout()
        form.addRow("Gemini API-nyckel:", self.api_key_input)
        form.addRow("Modell:", self.model_input)
        form.addRow("Global hotkey:", self.hotkey_input)

        self.error_label = QLineEdit()
        self.error_label.setReadOnly(True)
        self.error_label.setStyleSheet("color: red; border: none; background: transparent;")
        self.error_label.hide()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        api_key = self.api_key_input.text().strip()
        hotkey = self.hotkey_input.text().strip().lower()
        if not api_key:
            self._show_error("API-nyckel krävs.")
            return
        try:
            parse_hotkey(hotkey)
        except HotkeyParseError as exc:
            self._show_error(str(exc))
            return
        self._config.gemini_api_key = api_key
        self._config.model = self.model_input.currentText().strip() or "gemini-2.5-flash"
        self._config.hotkey = hotkey
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def result_config(self) -> Config:
        return self._config

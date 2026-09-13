from __future__ import annotations

import ctypes
import winreg
from dataclasses import dataclass, fields

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget


def qss(*rules: tuple[str, str]) -> str:
    """Builds a stylesheet from (selector, body) pairs.

    Keeps every brace in one place: f-string fragments that spell out `{{`/`}}` are far too
    easy to get wrong, and Qt silently drops the whole stylesheet when they are.
    """
    return "".join(f"{selector} {{ {body} }} " for selector, body in rules)


def css_variables(palette: "Palette") -> str:
    """The palette as CSS custom properties, so the web UI and the Qt chrome share one source."""
    return "".join(
        f"--{field.name.replace('_', '-')}:{getattr(palette, field.name)};" for field in fields(palette)
    )


@dataclass(frozen=True)
class Palette:
    """Design tokens for the 'paper' visual language (see design/LLM Overlay - Paper.dc.html)."""

    surface: str  # main panel / toolbar / dialog background
    surface_alt: str  # muted sub-panel background (input row, sidebar, subheader)
    elevated: str  # raised surface: selected segment, card on top of a muted row
    bubble: str  # user chat bubble / segmented-control track / inline code background
    border: str  # outer border of surfaces
    border_soft: str  # dividers, input borders
    ink: str  # primary text
    ink_soft: str  # secondary text / labels
    ink_faint: str  # placeholder / tertiary text
    accent: str  # single interactive accent (sage)
    accent_hover: str
    accent_on: str  # text/icon color placed on top of the accent
    knob: str  # toggle-switch knob
    danger_bg: str
    danger_border: str
    danger_text: str
    danger_text_soft: str
    danger_icon: str
    code_bg: str
    code_text: str
    scrollbar: str


LIGHT = Palette(
    surface="#FFFDF9",
    surface_alt="#FAF7F1",
    elevated="#FFFDF9",
    bubble="#F0ECE3",
    border="#DDD8CF",
    border_soft="#ECE7DE",
    ink="#2C2823",
    ink_soft="#5C564D",
    ink_faint="#8E8A82",
    accent="#4C6B5A",
    accent_hover="#3A5546",
    accent_on="#F7F9F5",
    knob="#FFFDF9",
    danger_bg="#F8F1EC",
    danger_border="#ECDCD2",
    danger_text="#5D3A3A",
    danger_text_soft="#6D5A55",
    danger_icon="#8A4F4F",
    code_bg="#F0ECE3",
    code_text="#42544A",
    scrollbar="#DDD8CF",
)

# Solid hex rather than rgba(): Qt's stylesheet parser treats fractional alpha unreliably,
# so the translucent whites from the design are pre-blended over the dark surface here.
DARK = Palette(
    surface="#18181B",
    surface_alt="#1C1C1F",
    elevated="#34343A",
    bubble="#27272B",
    border="#2F2F33",
    border_soft="#26262A",
    ink="#ECEAE6",
    ink_soft="#B7B2A8",
    ink_faint="#8E8A82",
    accent="#6B9481",
    accent_hover="#7FA895",
    accent_on="#0F1512",
    knob="#DEDCD8",
    danger_bg="#2A1D1B",
    danger_border="#4A322E",
    danger_text="#E4B8AE",
    danger_text_soft="#C9A79E",
    danger_icon="#D08E82",
    code_bg="#26262A",
    code_text="#A8C6B4",
    scrollbar="#38383D",
)

MODES = ("system", "light", "dark")

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def apply_titlebar_theme(widget: QWidget, dark: bool) -> None:
    """Matches the native title bar to the app theme (windows with system chrome, e.g. Settings)."""
    try:
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            int(widget.winId()),
            _DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except (AttributeError, OSError):
        pass  # older Windows without this DWM attribute: keep the default title bar


def _windows_uses_light_theme() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        with key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return bool(value)
    except OSError:
        return True


class ThemeManager(QObject):
    """Resolves the active palette from a user mode ('system'/'light'/'dark') and notifies listeners."""

    changed = Signal()

    def __init__(self, mode: str = "system", parent: QObject | None = None):
        super().__init__(parent)
        self.mode = mode if mode in MODES else "system"

    def resolved_mode(self) -> str:
        if self.mode == "system":
            return "light" if _windows_uses_light_theme() else "dark"
        return self.mode

    @property
    def palette(self) -> Palette:
        return LIGHT if self.resolved_mode() == "light" else DARK

    def set_mode(self, mode: str) -> None:
        if mode not in MODES or mode == self.mode:
            return
        self.mode = mode
        self.changed.emit()

    def cycle(self) -> None:
        """Used by the panel header's theme toggle: light -> dark -> system -> light..."""
        order = ["light", "dark", "system"]
        current = self.mode if self.mode in order else "light"
        self.mode = order[(order.index(current) + 1) % len(order)]
        self.changed.emit()

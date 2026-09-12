from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312

_MODIFIER_NAMES = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "super": MOD_WIN,
}

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL


class HotkeyParseError(ValueError):
    pass


def parse_hotkey(combo: str) -> tuple[int, int]:
    """Parse a string like 'ctrl+shift+o' into (modifiers, virtual_key_code)."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise HotkeyParseError(f"Empty hotkey combo: {combo!r}")
    *mod_parts, key_part = parts
    modifiers = 0
    for mod in mod_parts:
        if mod not in _MODIFIER_NAMES:
            raise HotkeyParseError(f"Unknown modifier {mod!r} in {combo!r}")
        modifiers |= _MODIFIER_NAMES[mod]
    if len(key_part) != 1 or not (key_part.isalnum()):
        raise HotkeyParseError(
            f"Unsupported key {key_part!r} in {combo!r} (only single letters/digits supported)"
        )
    vk = ord(key_part.upper())
    return modifiers, vk


class GlobalHotkey(QObject, QAbstractNativeEventFilter):
    triggered = Signal()

    def __init__(self, combo: str, hotkey_id: int = 1, parent: QObject | None = None):
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._modifiers, self._vk = parse_hotkey(combo)
        self._id = hotkey_id
        self._registered = False

    def register(self) -> bool:
        ok = bool(
            _user32.RegisterHotKey(
                None, self._id, self._modifiers | MOD_NOREPEAT, self._vk
            )
        )
        self._registered = ok
        return ok

    def unregister(self) -> None:
        if self._registered:
            _user32.UnregisterHotKey(None, self._id)
            self._registered = False

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self.triggered.emit()
        return False, 0

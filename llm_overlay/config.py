from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Settings, key and history live in the project root next to run.bat, not inside the package.
APP_DIR = Path(__file__).resolve().parents[1]
SETTINGS_PATH = APP_DIR / "settings.json"
ENV_PATH = APP_DIR / ".env"


@dataclass
class OverlayConfig:
    border_thickness: int = 8  # grab margin for moving the frame, not the drawn line
    line_width: int = 2
    corner_size: int = 16
    default_width: int = 400
    default_height: int = 300
    color: str = ""  # empty follows the theme's ink colour


@dataclass
class Config:
    gemini_api_key: str = ""
    model: str = "gemini-3.6-flash"
    hotkey: str = "ctrl+shift+o"
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    history_dir: str = "history"
    auto_send: bool = False
    auto_send_question: str = "Beskriv vad som visas i den här skärmdumpen."
    detail_level: str = "medel"
    thinking_level: str = "dynamic"
    save_history: bool = True
    theme: str = "system"

    @property
    def history_path(self) -> Path:
        return APP_DIR / self.history_dir


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def load_api_key(path: Path = ENV_PATH) -> str:
    env_value = os.environ.get("GEMINI_API_KEY")
    if env_value:
        return env_value
    return _parse_env_file(path).get("GEMINI_API_KEY", "")


def save_api_key(api_key: str, path: Path = ENV_PATH) -> None:
    lines = []
    found = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                lines.append(f"GEMINI_API_KEY={api_key}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"GEMINI_API_KEY={api_key}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(path: Path = SETTINGS_PATH) -> Config:
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    overlay_data = data.get("overlay", {})

    api_key = load_api_key()
    legacy_key = data.get("gemini_api_key", "").strip()
    if not api_key and legacy_key:
        # Migrate a key that was previously stored in settings.json into .env.
        save_api_key(legacy_key)
        api_key = legacy_key

    defaults = Config()
    return Config(
        gemini_api_key=api_key,
        model=data.get("model", defaults.model),
        hotkey=data.get("hotkey", defaults.hotkey),
        overlay=OverlayConfig(**overlay_data) if overlay_data else OverlayConfig(),
        history_dir=data.get("history_dir", defaults.history_dir),
        auto_send=data.get("auto_send", defaults.auto_send),
        auto_send_question=data.get("auto_send_question", defaults.auto_send_question),
        detail_level=data.get("detail_level", defaults.detail_level),
        thinking_level=data.get("thinking_level", defaults.thinking_level),
        save_history=data.get("save_history", defaults.save_history),
        theme=data.get("theme", defaults.theme),
    )


def save_config(config: Config, path: Path = SETTINGS_PATH) -> None:
    data = {
        "model": config.model,
        "hotkey": config.hotkey,
        "overlay": asdict(config.overlay),
        "history_dir": config.history_dir,
        "auto_send": config.auto_send,
        "auto_send_question": config.auto_send_question,
        "detail_level": config.detail_level,
        "thinking_level": config.thinking_level,
        "save_history": config.save_history,
        "theme": config.theme,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    save_api_key(config.gemini_api_key)


def has_api_key(config: Config) -> bool:
    return bool(config.gemini_api_key.strip())

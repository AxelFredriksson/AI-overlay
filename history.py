from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtGui import QPixmap


class HistoryStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.images_dir = base_dir / "images"
        self.log_path = base_dir / "history.jsonl"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def new_session_id(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{stamp}-{secrets.token_hex(3)}"

    def save_image(self, session_id: str, pixmap: QPixmap) -> Path:
        rel_path = Path("images") / f"{session_id}.png"
        pixmap.save(str(self.base_dir / rel_path), "PNG")
        return rel_path

    def append_turn(
        self,
        session_id: str,
        turn: int,
        image_path: Path,
        model: str,
        question: str,
        answer: str,
    ) -> None:
        record = {
            "session_id": session_id,
            "turn": turn,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "image_path": str(image_path).replace("\\", "/"),
            "model": model,
            "question": question,
            "answer": answer,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtGui import QPixmap


@dataclass
class SessionSummary:
    session_id: str
    first_question: str
    started_at: datetime
    turn_count: int
    image_path: Path | None


@dataclass
class HistoryTurn:
    turn: int
    timestamp: datetime
    question: str
    answer: str


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

    def _read_records(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        records = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def list_sessions(self) -> list[SessionSummary]:
        """Most-recent-first summary of every saved session (one entry per session_id)."""
        by_session: dict[str, list[dict]] = {}
        for record in self._read_records():
            by_session.setdefault(record["session_id"], []).append(record)

        summaries: list[SessionSummary] = []
        for session_id, records in by_session.items():
            records.sort(key=lambda r: r["turn"])
            first = records[0]
            image_rel = first.get("image_path")
            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    first_question=first["question"],
                    # Stored in UTC; callers display it, so hand them local time.
                    started_at=datetime.fromisoformat(first["timestamp"]).astimezone(),
                    turn_count=len(records),
                    image_path=(self.base_dir / image_rel) if image_rel else None,
                )
            )
        summaries.sort(key=lambda s: s.started_at, reverse=True)
        return summaries

    def load_session(self, session_id: str) -> list[HistoryTurn]:
        turns = [
            HistoryTurn(
                turn=r["turn"],
                timestamp=datetime.fromisoformat(r["timestamp"]).astimezone(),
                question=r["question"],
                answer=r["answer"],
            )
            for r in self._read_records()
            if r["session_id"] == session_id
        ]
        turns.sort(key=lambda t: t.turn)
        return turns

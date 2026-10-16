"""Conversation history: kept in memory and appended to a JSON-Lines log file."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class ConversationLogger:
    """One logger per chat session. Each turn is flushed to disk immediately,
    so the history survives even if the program is closed abruptly."""

    def __init__(self, log_dir: Optional[Path] = None, enabled: bool = True,
                 clock: Callable[[], datetime] = datetime.now):
        self._clock = clock
        self.enabled = enabled
        self.error: Optional[str] = None
        self.entries: List[dict] = []
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self.session_id = clock().strftime("%Y%m%d_%H%M%S")
        self.path = self.log_dir / f"session_{self.session_id}.jsonl"

    def add(self, speaker: str, text: str, intent: Optional[str] = None,
            confidence: Optional[float] = None) -> dict:
        entry = {
            "time": self._clock().isoformat(timespec="seconds"),
            "speaker": speaker,
            "text": text,
            "intent": intent,
            "confidence": confidence,
        }
        self.entries.append(entry)
        if self.enabled:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as exc:  # read-only folder, disk full, ...
                self.enabled = False
                self.error = str(exc)
        return entry

    def format_history(self) -> str:
        if not self.entries:
            return "(no messages yet)"
        lines = []
        for e in self.entries:
            stamp = e["time"][11:19]
            who = "You" if e["speaker"] == "user" else "Bot"
            lines.append(f"[{stamp}] {who}: {e['text']}")
        return "\n".join(lines)

    def export_text(self, path: Optional[Path] = None) -> Path:
        """Write the readable transcript to a .txt file and return its path."""
        target = Path(path) if path else self.path.with_suffix(".txt")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.format_history() + "\n", encoding="utf-8")
        return target

    @staticmethod
    def latest_session(log_dir: Optional[Path] = None) -> Optional[Path]:
        folder = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        files = sorted(folder.glob("session_*.jsonl")) if folder.exists() else []
        return files[-1] if files else None

    @staticmethod
    def read_session(path: Path) -> str:
        lines = []
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                e = json.loads(raw)
                who = "You" if e["speaker"] == "user" else "Bot"
                lines.append(f"[{e['time'][11:19]}] {who}: {e['text']}")
        return "\n".join(lines) if lines else "(empty session)"

"""Remembered per-book state (last page, reading direction, pairing) as JSON."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_ENTRIES = 1000


@dataclass
class BookState:
    page: int = 0
    rtl: bool | None = None  # None = follow the book's own hint
    cover_alone: bool = True


def default_state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "cbv" / "books.json"


class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_path()
        self._data: dict[str, dict] = {}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._data = loaded
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            log.warning("ignoring unreadable state file %s: %s", self.path, e)

    def get(self, key: str) -> BookState:
        entry = self._data.get(key)
        if not isinstance(entry, dict):
            return BookState()
        defaults = BookState()
        page = entry.get("page", defaults.page)
        rtl = entry.get("rtl", defaults.rtl)
        cover = entry.get("cover_alone", defaults.cover_alone)
        return BookState(
            page=page if isinstance(page, int) and page >= 0 else 0,
            rtl=rtl if isinstance(rtl, bool) else None,
            cover_alone=cover if isinstance(cover, bool) else True,
        )

    def put(self, key: str, state: BookState) -> None:
        self._data[key] = {**asdict(state), "seen": time.time()}
        if len(self._data) > _MAX_ENTRIES:
            oldest = sorted(self._data, key=lambda k: self._data[k].get("seen", 0))
            for k in oldest[: len(self._data) - _MAX_ENTRIES]:
                del self._data[k]

    def flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("cannot save state to %s: %s", self.path, e)

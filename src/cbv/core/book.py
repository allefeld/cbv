"""An opened comic book: archive, ordered pages, metadata and cached page sizes."""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

from ..archive import Archive, ArchiveError, open_archive
from ..metadata.merge import load_metadata
from ..metadata.model import Metadata
from ..pages import page_names
from ..render.decode import probe_size
from ..render.layout import Size

_BYTES_CACHE_LIMIT = 96 << 20
_PLACEHOLDER_SIZE: Size = (2, 3)


class Book:
    """Thread-safe: pages may be read and probed from worker threads."""

    def __init__(self, path: str) -> None:
        self.path = str(Path(path).resolve())
        self.archive: Archive = open_archive(self.path)
        try:
            self.page_names = page_names(self.archive.names())
            if not self.page_names:
                raise ArchiveError(f"no images found in {path}")
            self.metadata: Metadata = load_metadata(self.path, self.archive)
        except BaseException:
            self.archive.close()
            raise
        self._lock = threading.Lock()
        self._sizes: list[Size | None] = [None] * len(self.page_names)
        self._wide_hint: dict[int, bool] = {}
        for info in self.metadata.pages:
            if info.double_page and 0 <= info.index < len(self._sizes):
                self._wide_hint[info.index] = True
        self._broken: set[int] = set()
        self._bytes: OrderedDict[int, bytes] = OrderedDict()
        self._bytes_size = 0

    @property
    def count(self) -> int:
        return len(self.page_names)

    @property
    def state_key(self) -> str:
        """Stable identity for remembered state: the Calibre uuid survives moves."""
        if self.metadata.uuid:
            return f"uuid:{self.metadata.uuid}"
        return f"path:{self.path}"

    def page_bytes(self, index: int) -> bytes:
        with self._lock:
            data = self._bytes.get(index)
            if data is not None:
                self._bytes.move_to_end(index)
                return data
        data = self.archive.read(self.page_names[index])
        with self._lock:
            if index not in self._bytes:
                self._bytes[index] = data
                self._bytes_size += len(data)
                while self._bytes_size > _BYTES_CACHE_LIMIT and len(self._bytes) > 1:
                    _, old = self._bytes.popitem(last=False)
                    self._bytes_size -= len(old)
        return data

    def size(self, index: int) -> Size | None:
        with self._lock:
            return self._sizes[index]

    def sizes(self) -> list[Size | None]:
        with self._lock:
            return list(self._sizes)

    def wide_flags(self) -> list[bool]:
        with self._lock:
            return [
                self._wide_hint.get(i, False) or (s is not None and s[0] > s[1])
                for i, s in enumerate(self._sizes)
            ]

    def probe(self, index: int) -> Size:
        """Determine (and remember) a page's displayed size."""
        known = self.size(index)
        if known is not None:
            return known
        try:
            size = probe_size(self.page_bytes(index))
        except Exception:
            size = _PLACEHOLDER_SIZE  # undecodable page: keep the layout working
            with self._lock:
                self._broken.add(index)
        with self._lock:
            self._sizes[index] = size
        return size

    def is_broken(self, index: int) -> bool:
        with self._lock:
            return index in self._broken

    def close(self) -> None:
        self.archive.close()

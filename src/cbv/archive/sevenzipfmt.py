from __future__ import annotations

import threading

from .base import Archive, ArchiveError


_MEMORY_LIMIT = 4 << 30


class SevenZipArchive(Archive):
    """7z archives. They are usually solid, so all entries are decompressed once
    on first access and kept in memory instead of re-decompressing per page."""

    def __init__(self, path: str) -> None:
        import py7zr

        try:
            with py7zr.SevenZipFile(path) as z:
                self._names = [
                    i.filename.replace("\\", "/") for i in z.list() if not i.is_directory
                ]
        except Exception as e:
            raise ArchiveError(f"cannot open 7z archive {path}: {e}") from e
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, bytes] | None = None

    def names(self) -> list[str]:
        return list(self._names)

    def read(self, name: str) -> bytes:
        import py7zr
        from py7zr.io import BytesIOFactory

        with self._lock:
            if self._data is None:
                try:
                    factory = BytesIOFactory(limit=_MEMORY_LIMIT)
                    with py7zr.SevenZipFile(self._path) as z:
                        z.extract(factory=factory)
                    self._data = {
                        k.replace("\\", "/"): v.read() for k, v in factory.products.items()
                    }
                except Exception as e:
                    raise ArchiveError(f"cannot read 7z archive {self._path}: {e}") from e
            try:
                return self._data[name]
            except KeyError:
                raise ArchiveError(f"no such entry: {name}") from None

    def close(self) -> None:
        self._data = None

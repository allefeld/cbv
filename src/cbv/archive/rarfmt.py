from __future__ import annotations

import threading

from .base import Archive, ArchiveError


class RarArchive(Archive):
    """RAR (v4/v5) through the bundled UnRAR library of ``unrar2-cffi``."""

    def __init__(self, path: str) -> None:
        from unrar.cffi import rarfile

        try:
            self._rar = rarfile.RarFile(path)
        except Exception as e:
            raise ArchiveError(f"cannot open RAR archive {path}: {e}") from e
        self._lock = threading.Lock()
        self._infos = {
            name.replace("\\", "/"): (name, info)
            for name, info in self._rar.infos.items()
            if not info.is_dir()
        }

    def names(self) -> list[str]:
        return list(self._infos)

    def read(self, name: str) -> bytes:
        try:
            raw_name, _ = self._infos[name]
        except KeyError:
            raise ArchiveError(f"no such entry: {name}") from None
        with self._lock:
            try:
                return self._rar.read(raw_name)
            except Exception as e:
                raise ArchiveError(f"cannot read {name}: {e}") from e

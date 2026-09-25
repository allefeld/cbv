from __future__ import annotations

import tarfile
import threading

from .base import Archive, ArchiveError


class TarArchive(Archive):
    def __init__(self, path: str) -> None:
        try:
            self._tar = tarfile.open(path)
        except (tarfile.TarError, OSError) as e:
            raise ArchiveError(f"cannot open TAR archive {path}: {e}") from e
        self._lock = threading.Lock()
        self._members = {m.name.replace("\\", "/"): m for m in self._tar.getmembers() if m.isfile()}

    def names(self) -> list[str]:
        return list(self._members)

    def read(self, name: str) -> bytes:
        try:
            member = self._members[name]
        except KeyError:
            raise ArchiveError(f"no such entry: {name}") from None
        with self._lock:
            try:
                f = self._tar.extractfile(member)
                if f is None:
                    raise ArchiveError(f"not a regular file: {name}")
                return f.read()
            except (tarfile.TarError, OSError) as e:
                raise ArchiveError(f"cannot read {name}: {e}") from e

    def close(self) -> None:
        self._tar.close()

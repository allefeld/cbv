from __future__ import annotations

from pathlib import Path

from .base import Archive, ArchiveError


class FolderArchive(Archive):
    """A plain directory of images, treated like an archive."""

    def __init__(self, path: str) -> None:
        self._root = Path(path)
        self._names = sorted(
            p.relative_to(self._root).as_posix() for p in self._root.rglob("*") if p.is_file()
        )

    def names(self) -> list[str]:
        return list(self._names)

    def read(self, name: str) -> bytes:
        try:
            return (self._root / name).read_bytes()
        except OSError as e:
            raise ArchiveError(f"cannot read {name}: {e}") from e

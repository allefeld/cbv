"""Open comic book containers, detecting the real format from magic bytes."""

from __future__ import annotations

import os

from .base import Archive, ArchiveError

__all__ = ["Archive", "ArchiveError", "detect_format", "open_archive"]

_ZIP = (b"PK\x03\x04", b"PK\x05\x06")
_RAR = b"Rar!\x1a\x07"
_7Z = b"7z\xbc\xaf\x27\x1c"


def detect_format(path: str) -> str:
    """Return 'folder', 'zip', 'rar', '7z' or 'tar'; the extension is never trusted."""
    if os.path.isdir(path):
        return "folder"
    try:
        with open(path, "rb") as f:
            head = f.read(8)
            f.seek(257)
            tar_magic = f.read(5)
    except OSError as e:
        raise ArchiveError(f"cannot read {path}: {e}") from e
    if head.startswith(_ZIP):
        return "zip"
    if head.startswith(_RAR):
        return "rar"
    if head.startswith(_7Z):
        return "7z"
    if tar_magic == b"ustar":
        return "tar"
    raise ArchiveError(f"unsupported or unrecognised archive format: {path}")


def open_archive(path: str) -> Archive:
    fmt = detect_format(path)
    if fmt == "zip":
        from .zipfmt import ZipArchive

        return ZipArchive(path)
    if fmt == "rar":
        from .rarfmt import RarArchive

        return RarArchive(path)
    if fmt == "7z":
        from .sevenzipfmt import SevenZipArchive

        return SevenZipArchive(path)
    if fmt == "tar":
        from .tarfmt import TarArchive

        return TarArchive(path)
    from .folder import FolderArchive

    return FolderArchive(path)

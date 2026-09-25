from __future__ import annotations

import threading
import zipfile

from .base import Archive, ArchiveError

_UTF8_FLAG = 0x800
# Tried in order when a name was stored without the UTF-8 flag; zipfile has
# already decoded it as cp437, which is rarely what the creator meant.
_LEGACY_ENCODINGS = ("utf-8", "cp932", "gbk", "cp949")


def _display_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not (info.flag_bits & _UTF8_FLAG) and not name.isascii():
        try:
            raw = name.encode("cp437")
        except UnicodeEncodeError:
            pass
        else:
            for encoding in _LEGACY_ENCODINGS:
                try:
                    name = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
    return name.replace("\\", "/")


class ZipArchive(Archive):
    def __init__(self, path: str) -> None:
        try:
            self._zip = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError) as e:
            raise ArchiveError(f"cannot open ZIP archive {path}: {e}") from e
        self._lock = threading.Lock()
        self._infos: dict[str, zipfile.ZipInfo] = {}
        for info in self._zip.infolist():
            if not info.is_dir():
                self._infos[_display_name(info)] = info

    def names(self) -> list[str]:
        return list(self._infos)

    def read(self, name: str) -> bytes:
        try:
            info = self._infos[name]
        except KeyError:
            raise ArchiveError(f"no such entry: {name}") from None
        with self._lock:
            try:
                return self._zip.read(info)
            except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as e:
                raise ArchiveError(f"cannot read {name}: {e}") from e

    def close(self) -> None:
        self._zip.close()

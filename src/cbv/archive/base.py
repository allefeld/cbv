"""Archive abstraction shared by all container formats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType


class ArchiveError(Exception):
    """The container could not be opened or an entry could not be read."""


class Archive(ABC):
    """A read-only container of files, addressed by '/'-separated names."""

    @abstractmethod
    def names(self) -> list[str]:
        """All file entries (no directories), in stored order."""

    @abstractmethod
    def read(self, name: str) -> bytes:
        """Return the content of one entry. Must be safe to call from threads."""

    def close(self) -> None:
        """Release underlying resources."""

    def __enter__(self) -> Archive:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

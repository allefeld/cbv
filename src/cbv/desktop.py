"""Install/uninstall the desktop entry and icon into the user's XDG data dir.

pip, pipx and ``uv tool`` install only into a virtualenv and cannot place files where the
desktop looks for them, so this is done on request with ``cbv --install-desktop``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

DESKTOP_NAME = "cbv.desktop"
ICON_NAME = "cbv.svg"
_ICON_DIR = Path("icons/hicolor/scalable/apps")
_APP_DIR = Path("applications")


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def quote_exec(path: str) -> str:
    """Quote one Exec argument per the Desktop Entry specification."""
    if not any(c in path for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return path
    escaped = path.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    return '"' + escaped.replace("%", "%%") + '"'


def launcher_command() -> str:
    """The command a desktop entry should run to start this installation of cbv."""
    argv0 = Path(sys.argv[0])
    candidate = Path(os.path.abspath(argv0))
    if argv0.name == "cbv" and candidate.is_file() and os.access(candidate, os.X_OK):
        return quote_exec(str(candidate))
    found = shutil.which("cbv")
    if found:
        return quote_exec(found)
    return f"{quote_exec(sys.executable)} -m cbv"


def _read(name: str) -> str:
    return (resources.files("cbv") / "data" / name).read_text(encoding="utf-8")


def _run(*cmd: str) -> None:
    if shutil.which(cmd[0]):
        subprocess.run(cmd, check=False, capture_output=True)


def install(home: Path | None = None, set_default: bool = False, exec_command: str | None = None) -> list[Path]:
    home = home or data_home()
    desktop = home / _APP_DIR / DESKTOP_NAME
    icon = home / _ICON_DIR / ICON_NAME
    desktop.parent.mkdir(parents=True, exist_ok=True)
    icon.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(_read(DESKTOP_NAME).replace("@EXEC@", exec_command or launcher_command()), encoding="utf-8")
    icon.write_text(_read(ICON_NAME), encoding="utf-8")
    _run("update-desktop-database", str(desktop.parent))
    if set_default:
        for line in _read(DESKTOP_NAME).splitlines():
            if line.startswith("MimeType="):
                _run("xdg-mime", "default", DESKTOP_NAME, *[m for m in line[9:].split(";") if m])
    return [desktop, icon]


def uninstall(home: Path | None = None) -> list[Path]:
    home = home or data_home()
    removed = []
    for path in (home / _APP_DIR / DESKTOP_NAME, home / _ICON_DIR / ICON_NAME):
        if path.exists():
            path.unlink()
            removed.append(path)
    _run("update-desktop-database", str(home / _APP_DIR))
    return removed

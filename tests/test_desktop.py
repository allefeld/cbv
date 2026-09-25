from __future__ import annotations

from pathlib import Path

from cbv import desktop


def test_install_writes_entry_and_icon(tmp_path: Path):
    paths = desktop.install(home=tmp_path, exec_command="/opt/x/cbv")
    entry = (tmp_path / "applications" / "cbv.desktop").read_text()
    assert "Exec=/opt/x/cbv %f" in entry and "@EXEC@" not in entry
    assert "application/vnd.comicbook+zip" in entry and "application/vnd.comicbook-rar" in entry
    assert (tmp_path / "icons/hicolor/scalable/apps/cbv.svg").read_text().startswith("<svg")
    assert len(paths) == 2


def test_uninstall_removes_what_install_created(tmp_path: Path):
    desktop.install(home=tmp_path, exec_command="cbv")
    removed = desktop.uninstall(home=tmp_path)
    assert len(removed) == 2 and not any(p.exists() for p in removed)
    assert desktop.uninstall(home=tmp_path) == []  # idempotent


def test_exec_quoting():
    assert desktop.quote_exec("/usr/bin/cbv") == "/usr/bin/cbv"
    assert desktop.quote_exec("/home/a b/cbv") == '"/home/a b/cbv"'
    assert desktop.quote_exec('/x/"y"') == '"/x/\\"y\\""'


def test_data_home_honours_xdg(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert desktop.data_home() == tmp_path

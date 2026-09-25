from __future__ import annotations

import argparse
import sys

from . import __version__


def _info(path: str) -> int:
    from .archive import ArchiveError, detect_format, open_archive
    from .metadata.merge import load_metadata
    from .pages import page_names

    try:
        fmt = detect_format(path)
        with open_archive(path) as archive:
            pages = page_names(archive.names())
            meta = load_metadata(path, archive)
    except ArchiveError as e:
        print(f"cbv: {e}", file=sys.stderr)
        return 1
    print(f"format: {fmt}\npages:  {len(pages)}")
    for key, value in vars(meta).items():
        if value not in (None, [], {}):
            print(f"{key}: {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cbv", description="A clutter-free comic book viewer.")
    parser.add_argument("file", nargs="?", help="comic book archive (cbz, cbr, cb7, cbt) or folder")
    parser.add_argument("--fullscreen", action="store_true", help="start in full-screen mode")
    parser.add_argument("--page", type=int, metavar="N", help="start on page N (1-based)")
    parser.add_argument("--version", action="version", version=f"cbv {__version__}")
    parser.add_argument("--install-desktop", action="store_true", help="install the desktop entry and icon for the current user, then exit")
    parser.add_argument("--set-default", action="store_true", help="with --install-desktop: make cbv the default app for comic archives")
    parser.add_argument("--uninstall-desktop", action="store_true", help="remove the desktop entry and icon, then exit")
    parser.add_argument("--info", action="store_true", help="print format, page count and metadata, then exit")
    args = parser.parse_args(argv)
    if args.install_desktop or args.uninstall_desktop:
        from . import desktop

        paths = desktop.install(set_default=args.set_default) if args.install_desktop else desktop.uninstall()
        verb = "installed" if args.install_desktop else "removed"
        for path in paths:
            print(f"{verb} {path}")
        return 0
    if args.info:
        if args.file is None:
            parser.error("--info needs a file")
        return _info(args.file)
    from .ui.app import run

    return run(args.file, fullscreen=args.fullscreen, page=args.page)


if __name__ == "__main__":
    sys.exit(main())

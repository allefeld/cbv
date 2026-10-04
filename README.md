# cbv

A comic book viewer that shows the artwork and nothing else: no menus, toolbars or sidebars.
Everything else (zoom bubble, information, thumbnail gallery) is available on request.

- **Formats:** CBZ (ZIP), CBR (RAR), CB7 (7z), CBT (tar) and plain folders of images. The format is
  detected from the file's content, not its extension (a `.cbr` that is really a ZIP works).
  RAR 4 is tested; RAR 5 should work but is untested. No PDF support.
- **Images:** JPEG, PNG, WebP, GIF, BMP, TIFF and AVIF (whatever the installed Pillow can decode).
- **Metadata:** an embedded `ComicInfo.xml`, if present (see [Metadata](#metadata)).
- **Linux only so far** (developed and tested on X11).

## Install

No system packages are required: Qt, Pillow and the RAR/7z readers all come from wheels.

```bash
pipx install /path/to/cbv          # or: uv tool install /path/to/cbv
cbv --install-desktop              # optional: application-menu entry, icon, file associations
```

Update after changing the source: `pipx install --force /path/to/cbv` (the version number is not bumped
on every change, so a plain `pipx upgrade` would do nothing). Uninstall: `cbv --uninstall-desktop`, then
`pipx uninstall cbv`.

`--install-desktop` writes `~/.local/share/applications/cbv.desktop` and an icon under
`~/.local/share/icons`. pip-style installers cannot do this on their own. Add `--set-default` to make
cbv the default application for comic archives.

One thing pip cannot provide: Qt's X11 plugin needs a few system libraries, e.g. `libxcb-cursor0` on
Debian/Ubuntu. If cbv aborts with "could not load the Qt platform plugin xcb", install that.

## Command line

```
cbv [--fullscreen] [--page N] [FILE]     # FILE: archive or folder; without it a file dialog opens
cbv --info FILE                          # print format, page count and merged metadata, then exit
cbv --install-desktop [--set-default]    # see above
cbv --uninstall-desktop
cbv --version
```

`--page N` is 1-based and overrides the remembered page for that launch.

## Reading

The window shows only the page(s), scaled to fill the window (up as well as down, with high-quality
Lanczos resampling). The window title shows the book and the page, e.g. `Arzach — 2–3 / 8`; in fullscreen
a small semi-transparent indicator in the upper-left corner shows it instead (only while the mouse
pointer is visible, and not while the zoom bubble or an overlay is open).

**Single or two pages.** If two pages fit side by side when scaled to the full window height, two are
shown; otherwise one. In two-page mode the cover is shown alone and the rest is paired in order
(2+3, 4+5, …); a landscape page (or a ComicInfo `DoublePage`) is always shown alone and pairing restarts
after it. Pairing follows the order of the pages, not the numbers in the filenames. If a book has an
extra page at the start and the pairs come out off by one, press `O`.

**Page order.** Pages are sorted by file name, "naturally" and case-insensitively (`p2` before `p10`),
whatever order the archive stores them in. Hidden files, `__MACOSX`, `Thumbs.db` and non-image files are
ignored. Page numbers are simply positions in that order.

**Reading direction.** Left-to-right by default; a ComicInfo `Manga=YesAndRightToLeft` makes it
right-to-left. `R` toggles it for the current book. In right-to-left books the first page of a pair is
on the right and the arrow keys/click zones follow the screen (see below).

## Controls

Everything is also in the right-click menu, which shows the shortcuts.

| Turning pages | |
|---|---|
| Next / previous page | `Space` / `Shift+Space` or `Backspace`; mouse wheel down / up |
| Towards the screen's right / left | `→` / `←` (so in right-to-left books `←` is "next") |
| Click | right third of the window: towards the right; left third: towards the left |
| First / last page | `Home` / `End` |
| Go to page | `Ctrl+G` |

| View | |
|---|---|
| Full screen | `F`, `F11`, or click in the middle third of the window |
| Leave / close things | `Esc` closes an open screen, then the zoom bubble, then leaves fullscreen |
| Right-to-left, cover alone | `R`, `O` (both are remembered per book) |
| Open another book | `Ctrl+O`, or drop a file on the window |
| Quit | `Q` or `Ctrl+Q` |

In fullscreen the mouse pointer hides after two seconds without movement.

**Zoom bubble.** A round magnifier around the mouse pointer, showing the original full-resolution image,
so fine detail is crisp.

- `↑` or `Ctrl`+wheel up opens it and zooms in further; `↓` or `Ctrl`+wheel down zooms out, and
  zooming out past the minimum closes it. The zoom range is 1.25× to 10×.
- The bubble follows the mouse and grows with the zoom factor; it starts at 38% of the window's
  shorter side. There is no separate size setting.
- `Esc` or a left click closes it (the click does nothing else). Turning a page also closes it.

**Information screen** (`PgUp`). Title, series, authors, credits,
date, publisher, language, tags, page count, description, file name and folder. If the book has
ComicInfo bookmarks, a *Contents* list follows; click an entry to jump to that page. Any key other than
`PgUp`/`PgDn`, or a left click outside the links, returns to the page. The mouse wheel scrolls long text.

**Gallery** (`PgDn`). Every page as a thumbnail, filling the window (thumbnails appear as they are
made). The highlight starts on the current page and moves with `Space`, `Shift+Space`, `Backspace`,
`←`, `→`, `↑`, `↓` (a row), `Home`, `End`. `Enter` or a click opens that page; `Esc` closes the
gallery and stays on the current page. The mouse wheel scrolls one row of thumbnails per notch. The grid always runs left to right, also for right-to-left books.

`PgUp` and `PgDn` also switch directly from one screen to the other; pressing the same key again closes it.

## Metadata

The only metadata source is a **`ComicInfo.xml` inside the archive** (ComicRack/Anansi schema), as
written by comic managers or exported from Calibre. It gives title, authors, credits, series and
number, date, language, publisher, tags and description, plus the reading hints: right-to-left,
double-page flags and bookmarks (page entries with a `Bookmark` attribute). Calibre `metadata.opf`
sidecars are ignored, `metadata.db` is never read, and other metadata formats (ComicBookInfo, CoMet,
ACBF, …) are not read. Without a `ComicInfo.xml`, the file name serves as the title.

Descriptions keep basic formatting (bold, italic, underline, paragraphs, lists, quotes, line
breaks); all other markup is reduced to its text.

## Remembered state

There is no config file. cbv remembers, per book, the last page, the reading-direction override and the
"cover alone" setting in `$XDG_STATE_HOME/cbv/books.json` (normally `~/.local/state/cbv/books.json`),
for up to 1000 books, identified by their path. It does not remember the window size, fullscreen
state or which book was open last.

## Calibre

Run `cbv --install-desktop`. cbv is then listed under *Open with* in Calibre's book context menu for
CBZ/CBR books.

## Troubleshooting

- **Nothing happens / immediate exit:** run `cbv FILE` from a terminal; errors and warnings (for example
  about an undecodable page) are printed there. A page that cannot be decoded is shown as a dark
  placeholder and does not stop you reading.
- **Qt platform plugin "xcb" error:** see the note under [Install](#install).
- **Wrong page pairing:** press `O`. **Wrong direction:** press `R`.

## Development

```bash
uv run cbv FILE           # run from the source tree
uv run pytest -q          # tests run headless (offscreen Qt)
```

Tests that use the author's real Calibre comics library are skipped when it is not present.

## License

Copyright © 2026 Carsten Allefeld. cbv is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License, version 3 or (at your option) any later version. See
[LICENSE](LICENSE). It comes with no warranty. (PyQt6, which cbv uses, is also GPL-licensed.)

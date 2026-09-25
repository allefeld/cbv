# cbv

Single-file comic book viewer for the author's own use (PyQt6 + Pillow). Users' view of it is in
`README.md`; this file is what you need to change the code.

## Commands

```bash
uv run pytest -q                 # ~100 tests, headless (tests/conftest.py sets QT_QPA_PLATFORM=offscreen)
uv run cbv FILE                  # run from source; `uv run cbv --info FILE` prints format/pages/metadata
pipx install --force .           # the author's global install; the version is not bumped, so --force
```

Tests that need the real Calibre library (`/home/ca/Collection/Books & Stories/Comics`) skip if it is
missing. There is no linter configured.

## Hard constraints

- **No system packages.** Everything must come from PyPI wheels (installed via uv/pipx). That is why RAR
  uses `unrar2-cffi` (bundled UnRAR) rather than `rarfile`/`7z`/`unar`.
- **No PDF support**, **no `metadata.db`**, metadata only from `metadata.opf` and `ComicInfo.xml`
  (deliberately no CoMet/ACBF/ComicBookInfo).
- **The default view has no chrome.** New features go behind keys, the right-click menu or overlays.
- Fit-to-window scaling includes upscaling above 100%.

## Layout (`src/cbv/`)

- `archive/` – `Archive` interface (`names()`, `read()`, thread-safe); format detected by magic bytes.
  ZIP/TAR stdlib, RAR via `unrar2-cffi`, 7z via `py7zr` (decompressed once into memory), folder.
- `pages.py` – image filtering + natural sort (never trust stored order). `core/book.py` – `Book`: pages,
  metadata, lazily probed page sizes, small LRU of raw page bytes.
- `metadata/` – `opf.py`, `comicinfo.py`, `merge.py` (OPF wins for descriptive fields; ComicInfo owns
  reading hints), `richtext.py` (allow-list HTML sanitizer for descriptions), `model.py`.
- `render/layout.py` – **pure** pairing/fitting logic in device pixels (unit-tested, no Qt);
  `render/decode.py` – Pillow decode + Lanczos resize.
- `ui/pipeline.py` – worker pools, scaled-image cache, full-res cache, thumbnails. `ui/viewer.py` – the
  window (paint-only canvas, actions, mouse/wheel). `ui/magnifier.py`, `ui/info_overlay.py`,
  `ui/gallery.py`, `ui/overlay.py` (base). `state.py` – JSON per-book state. `desktop.py` – desktop entry.

## Things that are easy to get wrong

- **Page indexes are 0-based everywhere**, including `Viewer.open_path(page=)`; only the CLI `--page` and
  the UI text are 1-based. ComicInfo `Image` indexes refer to the sorted page list.
- **Geometry is in device pixels** (`Viewer._device_size()`, `Placement`); `paintEvent` scales the painter by
  `1/dpr` to draw pixel-exact.
- **Worker threads must never touch widgets or the pipeline's caches**; they emit signals and the main
  thread updates the cache (`RenderPipeline._on_scaled`). Keep `_cache_bytes` equal to the real sum: a
  drifting counter once evicted the pages on screen (regression tests in `tests/test_pipeline.py`).
- **Shortcuts are `QAction`s** with window scope. While an overlay is open, the navigation actions are
  disabled so keys reach it; the Info overlay disables *all* actions except `PgUp`/`PgDn` so that any
  other key closes it (`Overlay.captures_all_keys`).
- **Pointer visibility drives the fullscreen page indicator** (`_update_hud`); overlays and the bubble
  reset or hide the cursor explicitly. Overlays get their own arrow cursor.
- Pages are stored as `Format_RGB32` `QImage`s (built from Pillow "BGRX" bytes).

## Testing notes

- UI tests use `open_and_show`/`pump` from `tests/test_viewer.py`; send keys with `QTest.keyClick(viewer, …)`
  (to the *overlay* when one is open and has focus). The mouse pointer is faked by monkeypatching
  `viewer._pointer_pos`; fullscreen by monkeypatching `viewer.isFullScreen`.
- In ad-hoc headless scripts, never open a non-existent file: `QMessageBox.critical` blocks forever.

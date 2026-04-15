"""File-system watcher — auto-repack modified PDFs, auto-add new ones.

On start:  extracts all PDFs from zip so MD links and file browsers work.
While running: monitors resources/ for new/modified PDFs.
On stop:   packs everything back into zip for compact git storage.

Works on both Windows and Linux.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import metadata

Entry = dict[str, Any]

# Seconds of quiet after last modification before auto-repacking a PDF
_DEBOUNCE: float = 3.0
# Seconds between debounce checks
_POLL: float = 1.0


def _known_pdfs(library: str) -> set[str]:
    """Return set of PDF filenames referenced in the bib."""
    return {
        e.get("pdf", "").split("/")[-1]
        for e in metadata.load(library)
        if e.get("pdf")
    }


def _extract_all(library: str) -> int:
    """Extract every PDF from zip so they're accessible as loose files."""
    zp = metadata._zip_path(library)
    if not zp.exists():
        return 0
    import zipfile

    count = 0
    res = Path(library) / metadata.RESOURCES
    with zipfile.ZipFile(zp, "r") as zf:
        for name in zf.namelist():
            dest = res / name
            if not dest.exists():
                dest.write_bytes(zf.read(name))
                count += 1
    return count


def _add_loose_pdf(library: str, path: Path) -> Entry | None:
    """Create a bib entry for a manually-dropped PDF."""
    fname = path.name
    known = _known_pdfs(library)
    if fname in known:
        return None
    # Use filename (minus extension) as provisional title
    stem = path.stem.replace("_", " ").replace("-", " ")
    entry = metadata.add_entry(
        library,
        title=stem,
        pdf_filename=f"{metadata.RESOURCES}/{fname}",
    )
    print(f"  Auto-added: {entry['key']} — {stem}")
    return entry


class _Handler(FileSystemEventHandler):
    """React to PDF create / modify events in resources/."""

    def __init__(self, library: str) -> None:
        super().__init__()
        self.library = library
        # fname → last-modified timestamp (for debounce)
        self._pending: dict[str, float] = {}

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        p = Path(str(event.src_path))
        if p.suffix.lower() != ".pdf":
            return
        # New PDF dropped into folder
        _add_loose_pdf(self.library, p)
        self._pending[p.name] = time.monotonic()

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        p = Path(str(event.src_path))
        if p.suffix.lower() != ".pdf":
            return
        self._pending[p.name] = time.monotonic()

    def drain(self) -> int:
        """Repack PDFs that have been quiet for _DEBOUNCE seconds. Returns count."""
        now = time.monotonic()
        ready = [f for f, t in self._pending.items() if now - t >= _DEBOUNCE]
        if not ready:
            return 0
        entries = metadata.load(self.library)
        pdf_map: dict[str, Entry] = {
            e.get("pdf", "").split("/")[-1]: e for e in entries if e.get("pdf")
        }
        packed = 0
        res = Path(self.library) / metadata.RESOURCES
        for fname in ready:
            del self._pending[fname]
            loose = res / fname
            if not loose.exists():
                continue
            # Only repack if already tracked and not newly extracted in this session
            if fname not in pdf_map:
                continue
            e = pdf_map[fname]
            metadata.remove_from_pack(self.library, fname)
            import zipfile

            with zipfile.ZipFile(
                metadata._zip_path(self.library), "a", zipfile.ZIP_DEFLATED
            ) as zf:
                zf.write(str(loose), fname)
            loose.unlink()
            e["pdf"] = fname
            packed += 1
            print(f"  Repacked: {fname}")
        if packed:
            metadata.save(self.library, entries)
        return packed


def run(library: str) -> None:
    """Start the file watcher (blocking). Ctrl+C to stop."""
    res = Path(library) / metadata.RESOURCES
    res.mkdir(parents=True, exist_ok=True)

    # Extract all PDFs so they're clickable / browsable
    n = _extract_all(library)
    if n:
        print(f"Extracted {n} PDF(s) from archive.")

    handler = _Handler(library)
    observer = Observer()
    observer.schedule(handler, str(res), recursive=False)
    observer.start()
    print(f"Watching {res}  (Ctrl+C to stop)")
    print("  • Drop a PDF here to auto-add it to the library")
    print("  • Modified PDFs are auto-repacked after closing your viewer")

    try:
        while True:
            time.sleep(_POLL)
            handler.drain()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        # Pack everything back for compact git storage
        print("\nPacking loose PDFs…")
        packed = metadata.pack_all(library)
        if packed:
            print(f"Packed {packed} PDF(s) into archive.")
        print("Watcher stopped.")


def is_file_locked(path: Path) -> bool:
    """Check if a file is still open by another process (best-effort)."""
    if sys.platform == "win32":
        try:
            with open(path, "r+b"):
                return False
        except (OSError, PermissionError):
            return True
    else:
        import subprocess

        r = subprocess.run(
            ["lsof", "--", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        return bool(r.stdout.strip())

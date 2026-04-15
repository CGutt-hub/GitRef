"""Local HTTP server for browser extension / bookmarklet."""

from __future__ import annotations

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from . import metadata, fetcher, repo

_lib: str = ""


class _H(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/save": self.send_error(404); return
        length = int(self.headers.get("Content-Length", 0))
        if length > 1_000_000: self.send_error(413); return
        try: data: dict[str, Any] = json.loads(self.rfile.read(length))
        except json.JSONDecodeError: self.send_error(400, "Bad JSON"); return

        url: str = data.get("url", "")
        title: str = data.get("title", "")
        meta: dict[str, Any] = {}
        det = fetcher.detect_identifier(url) or fetcher.detect_identifier(title)
        if det:
            kind, val = det
            try:
                meta = {"doi": fetcher.fetch_doi, "arxiv": fetcher.fetch_arxiv,
                        "isbn": fetcher.fetch_isbn}[kind](val)
            except Exception: pass
        if not meta.get("title"): meta["title"] = title
        if not meta.get("url"): meta["url"] = url

        # Auto-download PDF
        pdf: str = fetcher.auto_download(meta, _lib)
        entry = metadata.add_entry(_lib, title=meta.get("title", title),
            authors=meta.get("authors"), year=meta.get("year"),
            doi=meta.get("doi"), url=meta.get("url", url),
            arxiv_id=meta.get("arxiv_id"), pdf_filename=pdf,
            abstract=meta.get("abstract"), journal=meta.get("journal"),
            extra={k: meta[k] for k in
            ("volume","number","pages","publisher","isbn","issn","booktitle") if meta.get(k)})
        if pdf:
            new = metadata.rename_pdf(_lib, entry)
            if new != pdf:
                entry["pdf"] = new
                entries = metadata.load(_lib)
                for e in entries:
                    if e["key"] == entry["key"]: e["pdf"] = new
                metadata.save(_lib, entries)
            packed = metadata.pack_pdf(_lib, entry)
            if packed:
                entries = metadata.load(_lib)
                for e in entries:
                    if e["key"] == entry["key"]: e["pdf"] = packed
                metadata.save(_lib, entries)

        self.send_response(200); self._cors()
        self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "title": entry["title"],
                                     "key": entry["key"], "file": entry.get("pdf", "")}).encode())
        print(f"  Saved: {entry['key']} — {entry['title']}" +
              (f" [{entry['pdf']}]" if entry.get("pdf") else ""))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format: str, /, *args: Any) -> None:  # noqa: A002
        pass


def run(library: str, port: int = 7342) -> None:
    global _lib
    _lib = library
    srv = HTTPServer(("127.0.0.1", port), _H)
    print(f"GitRef server on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try: srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\nFinal sync: {repo.sync(library)}")
    finally: srv.server_close()

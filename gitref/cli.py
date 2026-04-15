"""CLI entry point for GitRef."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import repo, metadata, fetcher, tui, server, watcher

DEFAULT_LIB: str = str(Path.home() / "GitRef")


def main() -> None:
    p = argparse.ArgumentParser(prog="gitref", description="Git-based reference manager")
    p.add_argument("-l", "--library", default=DEFAULT_LIB,
                   help=f"Library repo path (default: {DEFAULT_LIB})")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("init", help="Initialise a new library")
    a = sub.add_parser("add", help="Add by DOI, arXiv ID, ISBN, or URL")
    a.add_argument("identifier", help="DOI, arXiv ID, ISBN, or URL")
    a.add_argument("-t", "--tags", nargs="*", default=[])
    a.add_argument("--no-download", action="store_true", help="Skip file download")
    s = sub.add_parser("search", help="Search the library")
    s.add_argument("query")
    sub.add_parser("list", help="List all entries")
    sub.add_parser("sync", help="Git sync")
    sub.add_parser("browse", help="Open interactive TUI")
    sub.add_parser("collections", help="List tag collections")
    e = sub.add_parser("export", help="Export library")
    e.add_argument("format", nargs="?", default="ris", choices=["ris"])
    sv = sub.add_parser("serve", help="Start server for browser extension")
    sv.add_argument("-p", "--port", type=int, default=7342)
    o = sub.add_parser("open", help="Unpack a compacted PDF for reading/annotating")
    o.add_argument("key", help="Entry key")
    cl = sub.add_parser("close", help="Re-compact a PDF after use")
    cl.add_argument("key", help="Entry key")
    sub.add_parser("compact", help="Compress all uncompressed PDFs")
    sub.add_parser("watch", help="Watch resources/ — auto-add dropped PDFs, auto-repack on close")

    args = p.parse_args()
    lib: str = str(Path(args.library).resolve())

    if args.command == "init":
        repo.init_repo(lib); print(f"Initialised: {lib}")

    elif args.command == "add":
        if not Path(lib, "resources", ".resources.bib").exists(): repo.init_repo(lib)
        det = fetcher.detect_identifier(args.identifier)
        meta: dict[str, Any]
        if not det:
            if args.identifier.startswith("http"):
                meta = {"url": args.identifier, "title": args.identifier}
            else:
                print(f"Cannot detect identifier: {args.identifier}", file=sys.stderr); sys.exit(1)
        else:
            kind, val = det
            try:
                meta = {"doi": fetcher.fetch_doi, "arxiv": fetcher.fetch_arxiv,
                        "isbn": fetcher.fetch_isbn}[kind](val)
            except Exception as e:
                print(f"Fetch failed: {e}", file=sys.stderr); sys.exit(1)
        dupes = metadata.find_duplicates(lib, meta.get("title", ""), meta.get("doi", ""))
        if dupes:
            print(f"⚠ Possible duplicates: {[d['key'] for d in dupes]}")
        pdf: str = "" if args.no_download else fetcher.auto_download(meta, lib)
        if pdf: print(f"Downloaded: {pdf}")
        entry = metadata.add_entry(lib, title=meta.get("title", ""),
            authors=meta.get("authors"), year=meta.get("year"),
            doi=meta.get("doi"), url=meta.get("url"), arxiv_id=meta.get("arxiv_id"),
            tags=args.tags or None, pdf_filename=pdf, abstract=meta.get("abstract"),
            journal=meta.get("journal"), extra={k: meta[k] for k in
            ("volume", "number", "pages", "publisher", "isbn", "issn", "booktitle") if meta.get(k)})
        if pdf:
            new = metadata.rename_pdf(lib, entry)
            if new != pdf:
                entry["pdf"] = new
                entries = metadata.load(lib)
                for e2 in entries:
                    if e2["key"] == entry["key"]: e2["pdf"] = new
                metadata.save(lib, entries)
            packed = metadata.pack_pdf(lib, entry)
            if packed:
                entries = metadata.load(lib)
                for e2 in entries:
                    if e2["key"] == entry["key"]: e2["pdf"] = packed
                metadata.save(lib, entries)
        print(f"Added: {entry['key']} \u2014 {entry['title']}")

    elif args.command == "search":
        for e in metadata.find(lib, args.query):
            auth = ", ".join(e.get("authors", [])[:2])
            print(f"  [{e.get('year', '')}] {auth} — {e.get('title', '')}")

    elif args.command == "list":
        for e in metadata.load(lib):
            auth = ", ".join(e.get("authors", [])[:2])
            print(f"  [{e.get('year', '')}] {e.get('key', '')} | {auth} — {e.get('title', '')}")

    elif args.command == "collections":
        for tag, n in metadata.collections(lib).items():
            print(f"  {tag} ({n})")

    elif args.command == "export":
        entries = metadata.load(lib)
        out = Path(lib) / f"library.{args.format}"
        out.write_text(metadata.export_ris(entries), encoding="utf-8")
        print(f"Exported {len(entries)} entries → {out}")

    elif args.command == "sync":
        print(f"Sync: {repo.sync(lib)}")

    elif args.command == "serve":
        server.run(lib, port=args.port)

    elif args.command == "open":
        entries = metadata.load(lib)
        e = next((x for x in entries if x["key"] == args.key), None)
        if not e: print(f"Entry not found: {args.key}", file=sys.stderr); sys.exit(1)
        if not e.get("pdf"): print("No file attached.", file=sys.stderr); sys.exit(1)
        metadata.open_pdf(lib, e, entries)
        print(f"Opened: {e['pdf']}")

    elif args.command == "close":
        entries = metadata.load(lib)
        e = next((x for x in entries if x["key"] == args.key), None)
        if not e: print(f"Entry not found: {args.key}", file=sys.stderr); sys.exit(1)
        if not e.get("pdf"): print("No file attached.", file=sys.stderr); sys.exit(1)
        metadata.close_pdf(lib, e, entries)
        print(f"Packed: {e['pdf']}")

    elif args.command == "compact":
        n = metadata.pack_all(lib)
        print(f"Packed {n} PDF(s) into archive.")

    elif args.command == "watch":
        if not Path(lib, "resources", ".resources.bib").exists(): repo.init_repo(lib)
        watcher.run(lib)

    elif args.command == "browse" or args.command is None:
        if not Path(lib, "resources", ".resources.bib").exists(): repo.init_repo(lib)
        tui.run(lib)


if __name__ == "__main__": main()

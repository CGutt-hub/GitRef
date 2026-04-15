"""Terminal UI — list, search, detail, tag, sort, collections, export, watch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from . import metadata, repo, fetcher

Entry = dict[str, Any]
con = Console()


def _table(entries: list[Entry], hl: str = "") -> Table:
    t = Table(box=box.SIMPLE_HEAVY, expand=True, title="GitRef Library",
              title_style="bold cyan", show_lines=False)
    t.add_column("#", style="dim", width=4, justify="right")
    t.add_column("Key", width=16, style="cyan")
    t.add_column("Year", width=5)
    t.add_column("Authors", ratio=2)
    t.add_column("Title", ratio=4)
    t.add_column("Tags", ratio=1, style="green")
    t.add_column("📎", width=2, justify="center")
    for i, e in enumerate(entries, 1):
        auth = ", ".join(e.get("authors",[])[:2])
        if len(e.get("authors",[])) > 2: auth += " et al."
        tags = ", ".join(e.get("tags",[]))
        pdf = "✓" if e.get("pdf") else ""
        title = e.get("title","")
        if hl and hl.lower() in title.lower():
            title = Text(title)
            idx = title.plain.lower().find(hl.lower())
            title.stylize("bold yellow", idx, idx+len(hl))
        t.add_row(str(i), e.get("key",""), e.get("year",""), auth, title, tags, pdf)
    return t

def _detail(e: Entry, library: str) -> None:
    l = [f"[bold]{e.get('title','')}[/bold]"]
    l.append(f"[cyan]{e.get('key','')}[/cyan]  [{e.get('type','misc')}]")
    if e.get("authors"): l.append(f"Authors: {', '.join(e['authors'])}")
    for k,label in [("year","Year"),("journal","Journal"),("booktitle","In"),
                     ("publisher","Publisher"),("volume","Vol"),("number","No"),
                     ("pages","Pages"),("doi","DOI"),("isbn","ISBN"),
                     ("arxiv_id","arXiv"),("url","URL")]:
        if e.get(k): l.append(f"{label}: {e[k]}")
    if e.get("tags"): l.append(f"Tags: [green]{', '.join(e['tags'])}[/green]")
    if e.get("pdf"): l.append(f"File: {e['pdf']}")
    if e.get("abstract"): l.append(f"\n[dim]{e['abstract'][:600]}[/dim]")
    con.print(Panel("\n".join(l), border_style="cyan"))

def _add(library: str) -> None:
    con.print("[cyan]Add — paste DOI, arXiv ID, ISBN, or URL.[/cyan]")
    raw = prompt("Identifier / URL: ").strip()
    if not raw: return
    detected = fetcher.detect_identifier(raw)
    meta = {}
    if detected:
        kind, val = detected
        try:
            con.print(f"[dim]Fetching {kind}…[/dim]")
            meta = {"doi": fetcher.fetch_doi, "arxiv": fetcher.fetch_arxiv,
                    "isbn": fetcher.fetch_isbn}[kind](val)
            con.print(f"[green]Found:[/green] {meta.get('title','')}")
        except Exception as exc:
            con.print(f"[red]Fetch failed: {exc}[/red]")
    if not meta.get("title"):
        meta["title"] = raw if not raw.startswith("http") else prompt("Title: ").strip()
        if not detected and raw.startswith("http"):
            meta["url"] = raw
    # Duplicate check
    dupes = metadata.find_duplicates(library, meta.get("title",""), meta.get("doi",""))
    if dupes:
        con.print(f"[yellow]⚠ Possible duplicate(s):[/yellow]")
        for d in dupes: con.print(f"  {d.get('key')}: {d.get('title','')}")
        if prompt("Add anyway? [y/N]: ").strip().lower() != "y": return
    tags_raw = prompt("Tags (comma-sep, empty to skip): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
    # Auto-download PDF / snapshot
    con.print("[dim]Downloading file…[/dim]")
    pdf = fetcher.auto_download(meta, library)
    if pdf: con.print(f"[green]Saved: {pdf}[/green]")
    else: con.print("[dim]No file downloaded.[/dim]")
    entry = metadata.add_entry(library, title=meta.get("title",""),
        authors=meta.get("authors"), year=meta.get("year"),
        doi=meta.get("doi"), url=meta.get("url"), arxiv_id=meta.get("arxiv_id"),
        tags=tags, pdf_filename=pdf, abstract=meta.get("abstract"),
        journal=meta.get("journal"), extra={k: meta[k] for k in
        ("volume","number","pages","publisher","isbn","issn","booktitle") if meta.get(k)})
    # Auto-rename PDF then pack into zip
    if pdf:
        new_pdf = metadata.rename_pdf(library, entry)
        if new_pdf != pdf:
            entry["pdf"] = new_pdf
            entries = metadata.load(library)
            for e in entries:
                if e["key"] == entry["key"]: e["pdf"] = new_pdf
            metadata.save(library, entries)
            con.print(f"[dim]Renamed → {new_pdf}[/dim]")
        packed = metadata.pack_pdf(library, entry)
        if packed:
            entries = metadata.load(library)
            for e in entries:
                if e["key"] == entry["key"]: e["pdf"] = packed
            metadata.save(library, entries)
            con.print(f"[dim]Packed into archive[/dim]")
    con.print(f"[green]Added: {entry['key']}[/green]")

def _get_entry(entries: list[Entry]) -> Entry | None:
    s = prompt("Entry # or key: ").strip()
    try: return entries[int(s)-1]
    except (ValueError, IndexError): pass
    for e in entries:
        if e["key"] == s: return e
    con.print("[red]Not found.[/red]")
    return None

def _sort(entries: list[Entry], key: str) -> list[Entry]:
    rev = key.startswith("-")
    k = key.lstrip("-")
    if k == "author":
        return sorted(entries, key=lambda e: (e.get("authors") or [""])[0].lower(), reverse=rev)
    return sorted(entries, key=lambda e: e.get(k, "").lower(), reverse=rev)

def run(library: str) -> None:
    cmds = WordCompleter(["list","search","add","detail","tag","delete",
        "collections","export","sort","sync","open","close","compact","watch","quit","help"], ignore_case=True)
    con.print(Panel("[bold cyan]GitRef[/bold cyan] — git-based reference manager", border_style="cyan"))
    con.print("[dim]Type 'help' for commands.[/dim]\n")
    sort_key = "year"
    while True:
        try: cmd = prompt("gitref> ", completer=cmds).strip()
        except (EOFError, KeyboardInterrupt): break
        c = cmd.split()
        c0 = c[0].lower() if c else ""
        if c0 in ("q","quit","exit"): break
        elif c0 in ("h","help"):
            con.print("[cyan]Commands:[/cyan]\n"
                "  list              show all (sorted)\n"
                "  search <q>        search entries\n"
                "  add               add reference (DOI/arXiv/ISBN/URL)\n"
                "  detail [#|key]    full entry details\n"
                "  tag [#|key]       edit tags\n"
                "  delete [#|key]    remove entry\n"
                "  collections       list tag-based collections\n"
                "  sort <field>      set sort (year/title/author, -field = desc)\n"
                "  export [ris]      export library\n"
                "  open [#|key]      unpack PDF for reading/annotating\n"
                "  close [#|key]     re-compact PDF after use\n"
                "  compact           compress all loose PDFs\n"
                "  watch             auto-add/repack (extracts all PDFs first)\n"
                "  sync              git sync\n"
                "  quit              exit")
        elif c0 == "list":
            entries = _sort(metadata.load(library), sort_key)
            con.print(_table(entries)) if entries else con.print("[dim]Empty library.[/dim]")
        elif c0 == "search":
            q = " ".join(c[1:]) or prompt("Search: ").strip()
            if q:
                entries = _sort(metadata.find(library, q), sort_key)
                con.print(_table(entries, hl=q))
                con.print(f"[dim]{len(entries)} result(s)[/dim]")
        elif c0 == "add": _add(library)
        elif c0 == "detail":
            entries = _sort(metadata.load(library), sort_key)
            e = _get_entry(entries) if len(c) < 2 else None
            if len(c) >= 2:
                try: e = entries[int(c[1])-1]
                except (ValueError, IndexError):
                    e = next((x for x in entries if x["key"]==c[1]), None)
            if e: _detail(e, library)
        elif c0 == "tag":
            entries = metadata.load(library)
            e = _get_entry(entries)
            if e:
                cur = ", ".join(e.get("tags",[]))
                raw = prompt(f"Tags [{cur}]: ").strip()
                if raw:
                    e["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
                    metadata.save(library, entries)
                    con.print("[green]Tags updated.[/green]")
        elif c0 == "delete":
            entries = metadata.load(library)
            e = _get_entry(entries)
            if e and prompt(f"Delete '{e.get('title','')}'? [y/N]: ").strip().lower() == "y":
                metadata.remove_entry(library, e["key"])
                con.print("[green]Deleted.[/green]")
        elif c0 == "collections":
            cols = metadata.collections(library)
            if cols:
                for tag, n in cols.items(): con.print(f"  [green]{tag}[/green] ({n})")
            else: con.print("[dim]No tags yet.[/dim]")
        elif c0 == "sort":
            sort_key = c[1] if len(c)>1 else prompt("Sort by (year/title/author, -field=desc): ").strip()
            con.print(f"[dim]Sorting by: {sort_key}[/dim]")
        elif c0 == "export":
            entries = metadata.load(library)
            fmt = c[1] if len(c)>1 else "ris"
            if fmt == "ris":
                out = Path(library) / "library.ris"
                out.write_text(metadata.export_ris(entries), encoding="utf-8")
                con.print(f"[green]Exported {len(entries)} entries → library.ris[/green]")
            else: con.print("[dim]Supported: ris[/dim]")
        elif c0 == "sync":
            con.print(f"[green]Sync: {repo.sync(library)}[/green]")
        elif c0 == "open":
            entries = metadata.load(library)
            e = _get_entry(entries)
            if e:
                if not e.get("pdf"): con.print("[dim]No file attached.[/dim]")
                else:
                    metadata.open_pdf(library, e, entries)
                    con.print(f"[green]Opened: {e['pdf']}[/green]")
        elif c0 == "close":
            entries = metadata.load(library)
            e = _get_entry(entries)
            if e:
                if not e.get("pdf"): con.print("[dim]No file attached.[/dim]")
                else:
                    metadata.close_pdf(library, e, entries)
                    con.print(f"[green]Packed: {e['pdf']}[/green]")
        elif c0 == "compact":
            n = metadata.pack_all(library)
            con.print(f"[green]Packed {n} PDF(s) into archive.[/green]")
        elif c0 == "watch":
            from . import watcher
            con.print("[cyan]Starting watcher… (Ctrl+C to stop and repack)[/cyan]")
            watcher.run(library)
        else: con.print("[dim]Unknown command. Type 'help'.[/dim]")

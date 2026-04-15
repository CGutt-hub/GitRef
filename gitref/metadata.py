"""BibTeX-backed resource metadata — single source of truth, no external libs."""

import os
import re
import subprocess
import sys
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

BIB: str = "resources/.resources.bib"
RESOURCES: str = "resources"
PACK: str = "resources/.resources.zip"

Entry = dict[str, Any]

# ── BibTeX parser ───────────────────────────────────────────────

def _parse_bib(text: str) -> list[dict[str, Any]]:
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{([^,]+),", text):
        etype, key = m.group(1).lower(), m.group(2).strip()
        start, depth, pos = m.end(), 1, m.end()
        while pos < len(text) and depth:
            depth += (text[pos] == "{") - (text[pos] == "}")
            pos += 1
        body = text[start:pos - 1]
        fields = {}
        for fm in re.finditer(
            r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|(\d+))", body
        ):
            k = fm.group(1).lower()
            fields[k] = (fm.group(2) or fm.group(3) or fm.group(4) or "").strip()
        raw_auth = fields.pop("author", "")
        raw_kw = fields.pop("keywords", "")
        fields.pop("eprinttype", None)
        # Map biblatex aliases to standard fields
        if "date" in fields and "year" not in fields:
            fields["year"] = fields.pop("date").split("-")[0]
        else:
            fields.pop("date", None)
        if "journaltitle" in fields and "journal" not in fields:
            fields["journal"] = fields.pop("journaltitle")
        else:
            fields.pop("journaltitle", None)
        fields.pop("langid", None)
        e = {"key": key, "type": etype,
             "authors": [a.strip() for a in raw_auth.split(" and ") if a.strip()],
             "tags": [t.strip() for t in raw_kw.split(",") if t.strip()]}
        for f in ("title","year","doi","url","journal","booktitle","publisher",
                   "volume","number","pages","isbn","issn","abstract","note",
                   "editor","edition","series","month","school","institution",
                   "howpublished","chapter"):
            e[f] = fields.pop(f, "")
        e["arxiv_id"] = fields.pop("eprint", "")
        e["pdf"] = fields.pop("file", "")
        if fields:
            e["extra"] = fields
        entries.append(e)
    return entries


def _write_bib(entries: list[dict[str, Any]]) -> str:
    parts = []
    for e in entries:
        lines = [f"@{e.get('type','misc')}{{{e['key']},"]
        def f(k, v):
            if v: lines.append(f"  {k} = {{{v}}},")
        f("title", e.get("title"))
        if e.get("authors"): f("author", " and ".join(e["authors"]))
        for k in ("year","journal","booktitle","publisher","volume","number",
                   "pages","doi","isbn","issn","url","abstract","note",
                   "editor","edition","series","month","school","institution",
                   "howpublished","chapter"):
            f(k, e.get(k))
        if e.get("tags"): f("keywords", ", ".join(e["tags"]))
        if e.get("pdf"): f("file", e["pdf"])
        if e.get("arxiv_id"):
            f("eprint", e["arxiv_id"]); f("eprinttype", "arxiv")
        for k, v in e.get("extra", {}).items(): f(k, v)
        lines.append("}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n" if parts else ""

# ── Helpers ─────────────────────────────────────────────────────

def _make_key(title: str, authors: list[str], year: str, taken: set[str]) -> str:
    last = re.sub(r"[^a-z]", "", (authors[0].split()[-1] if authors
                  else (title.split() or ["x"])[0]).lower())
    base = f"{last}{year}"
    key, s = base, ord("a")
    while key in taken:
        key = f"{base}{chr(s)}"; s += 1
    return key

def _auto_type(e: Entry) -> str:
    if e.get("isbn"): return "book"
    if e.get("booktitle"): return "inproceedings"
    if e.get("school"): return "phdthesis"
    if e.get("journal") or e.get("arxiv_id"): return "article"
    return "misc"

def _safe(text: str, n: int = 60) -> str:
    return re.sub(r"\s+", "_", re.sub(r"[^a-zA-Z0-9 _-]", "", text)).strip("_")[:n]

# ── Public API ──────────────────────────────────────────────────

def _regen(repo: str) -> None:
    """Auto-regenerate resources.md and README.md after any bib change."""
    try:
        from . import build_readme
        build_readme.update_readme(repo)
    except Exception:
        pass

def load(repo: str) -> list[Entry]:
    p = Path(repo) / BIB
    return _parse_bib(p.read_text(encoding="utf-8")) if p.exists() else []

def save(repo: str, entries: list[Entry]) -> None:
    (Path(repo) / BIB).write_text(_write_bib(entries), encoding="utf-8")
    _regen(repo)

def add_entry(
    repo: str, title: str = "", authors: list[str] | None = None,
    year: str | int | None = None, doi: str | None = None, url: str | None = None,
    arxiv_id: str | None = None, tags: list[str] | None = None,
    pdf_filename: str | None = None, abstract: str | None = None,
    journal: str | None = None, extra: dict[str, str] | None = None,
) -> Entry:
    entries = load(repo)
    yr = str(year) if year else ""
    auth = authors or []
    e = {"key": _make_key(title, auth, yr, {x["key"] for x in entries}),
         "title": title, "authors": auth, "year": yr,
         "doi": doi or "", "url": url or "", "arxiv_id": arxiv_id or "",
         "journal": journal or "", "abstract": abstract or "",
         "tags": tags or [], "pdf": pdf_filename or "",
         "booktitle":"","publisher":"","volume":"","number":"","pages":"",
         "isbn":"","issn":"","note":"","editor":"","edition":"","series":"",
         "month":"","school":"","institution":"","howpublished":"","chapter":""}
    if extra: e.update(extra)
    e["type"] = _auto_type(e)
    entries.append(e)
    save(repo, entries)
    return e

def remove_entry(repo: str, key: str) -> bool:
    entries = load(repo)
    new = [e for e in entries if e["key"] != key]
    if len(new) < len(entries):
        # Also remove from zip if present
        for e in entries:
            if e["key"] == key and e.get("pdf"):
                remove_from_pack(repo, e["pdf"].split("/")[-1])
                break
        save(repo, new)
        return True
    return False

def find(repo: str, query: str) -> list[Entry]:
    q = query.lower()
    return [e for e in load(repo) if q in " ".join([
        e.get("title",""), " ".join(e.get("authors",[])),
        " ".join(e.get("tags",[])), e.get("doi",""), e.get("arxiv_id",""),
        e.get("journal",""), e.get("booktitle",""), e.get("isbn",""),
        e.get("key",""),
    ]).lower()]

# ── PDF rename ──────────────────────────────────────────────────

def rename_pdf(repo: str, entry: Entry) -> str:
    old = entry.get("pdf", "")
    if not old: return old
    # Resolve actual file path (could be "resources/x.pdf" or just "x.pdf")
    src = Path(repo) / old
    if not src.exists():
        src = Path(repo) / RESOURCES / old.split("/")[-1]
    if not src.exists(): return old
    a = _safe(entry["authors"][0].split()[-1]) if entry.get("authors") else "unknown"
    name = f"{a}_{entry.get('year','')}_{_safe(entry.get('title',''),40)}{src.suffix}"
    new = Path(repo) / RESOURCES / name
    new.parent.mkdir(parents=True, exist_ok=True)
    src.rename(new)
    return f"{RESOURCES}/{name}"

# ── Zip archive ─────────────────────────────────────────────────

def _zip_path(repo: str) -> Path:
    return Path(repo) / PACK

def pack_pdf(repo: str, entry: Entry) -> str:
    """Add a loose PDF into .resources.zip and remove the loose file. Returns filename stored."""
    pdf = entry.get("pdf", "")
    if not pdf: return ""
    src = Path(repo) / pdf
    if not src.exists(): return pdf
    fname = src.name
    zp = _zip_path(repo)
    with zipfile.ZipFile(zp, "a", zipfile.ZIP_DEFLATED) as zf:
        # Remove old version if present (rewrite needed for true removal, but
        # adding a duplicate name overwrites on next read via namelist dedup)
        zf.write(str(src), fname)
    src.unlink()
    return fname

def unpack_pdf(repo: str, entry: Entry) -> str:
    """Extract a PDF from .resources.zip to resources/. Returns extracted relative path or ''."""
    pdf = entry.get("pdf", "")
    if not pdf: return ""
    zp = _zip_path(repo)
    if not zp.exists(): return ""
    with zipfile.ZipFile(zp, "r") as zf:
        if pdf not in zf.namelist(): return ""
        data = zf.read(pdf)
    dest = Path(repo) / RESOURCES / pdf
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return f"{RESOURCES}/{pdf}"

def remove_from_pack(repo: str, filename: str) -> None:
    """Remove a file from .resources.zip by rewriting without it."""
    zp = _zip_path(repo)
    if not zp.exists(): return
    tmp = zp.with_suffix(".tmp")
    with zipfile.ZipFile(zp, "r") as zf_in, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf_out:
        for item in zf_in.infolist():
            if item.filename != filename:
                zf_out.writestr(item, zf_in.read(item.filename))
    tmp.replace(zp)

def pack_all(repo: str) -> int:
    """Pack all loose PDFs in resources/ into .resources.zip. Returns count."""
    res = Path(repo) / RESOURCES
    entries = load(repo)
    pdf_map = {e.get("pdf", "").split("/")[-1]: e for e in entries if e.get("pdf")}
    loose = list(res.glob("*.pdf"))
    if not loose:
        return 0
    zp = _zip_path(repo)
    # Collect existing zip contents to avoid duplicates
    existing: set[str] = set()
    if Path(zp).exists():
        with zipfile.ZipFile(zp, "r") as zf:
            existing = set(zf.namelist())
    # Pack all loose PDFs in one batch
    with zipfile.ZipFile(zp, "a", zipfile.ZIP_DEFLATED) as zf:
        for f in loose:
            fname = f.name
            if fname not in existing:
                zf.write(str(f), fname)
            f.unlink()
            if fname in pdf_map:
                pdf_map[fname]["pdf"] = fname
    save(repo, entries)
    return len(loose)

def open_pdf(repo: str, entry: Entry, entries: list[Entry]) -> str:
    """Extract from zip if needed, then launch in system viewer."""
    pdf = entry.get("pdf", "")
    if not pdf: return ""
    loose = Path(repo) / RESOURCES / pdf.split("/")[-1]
    if not loose.exists():
        # Try extracting from zip
        extracted = unpack_pdf(repo, entry)
        if not extracted: return ""
        loose = Path(repo) / extracted
    if not loose.exists(): return ""
    if sys.platform == "win32":
        os.startfile(str(loose))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(loose)])
    else:
        subprocess.Popen(["xdg-open", str(loose)])
    return str(loose)

def close_pdf(repo: str, entry: Entry, entries: list[Entry]) -> str:
    """Re-pack a loose PDF back into the zip (preserving annotations). Returns packed name."""
    pdf = entry.get("pdf", "")
    if not pdf: return ""
    fname = pdf.split("/")[-1]
    loose = Path(repo) / RESOURCES / fname
    if not loose.exists(): return pdf
    # Store back into zip
    entry["pdf"] = fname
    zp = _zip_path(repo)
    # Rewrite zip: remove old version, add updated file
    remove_from_pack(repo, fname)
    with zipfile.ZipFile(zp, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(str(loose), fname)
    loose.unlink()
    save(repo, entries)
    return fname

# ── Reconcile (detect deleted PDFs) ─────────────────────────────

def reconcile(repo: str) -> int:
    """Clear file refs for PDFs not on disk or in zip. Returns count."""
    entries = load(repo)
    zp = _zip_path(repo)
    zip_names = set()
    if zp.exists():
        with zipfile.ZipFile(zp, "r") as zf:
            zip_names = set(zf.namelist())
    cleaned = 0
    for e in entries:
        pdf = e.get("pdf", "")
        if not pdf: continue
        fname = pdf.split("/")[-1]
        # Check loose file or in zip
        if not (Path(repo) / RESOURCES / fname).exists() and fname not in zip_names:
            e["pdf"] = ""
            cleaned += 1
    if cleaned:
        save(repo, entries)
    return cleaned

# ── Duplicates ──────────────────────────────────────────────────

def find_duplicates(repo: str, title: str = "", doi: str = "", threshold: float = 0.85) -> list[Entry]:
    return [e for e in load(repo) if
            (doi and e.get("doi") and e["doi"].lower() == doi.lower()) or
            (title and e.get("title") and
             SequenceMatcher(None, title.lower(), e["title"].lower()).ratio() >= threshold)]

# ── Collections (tag-based) ─────────────────────────────────────

def collections(repo: str) -> dict[str, int]:
    c: dict[str, int] = {}
    for e in load(repo):
        for t in e.get("tags", []): c[t] = c.get(t, 0) + 1
    return dict(sorted(c.items()))

# ── RIS export ──────────────────────────────────────────────────

_RIS = {"article":"JOUR","book":"BOOK","inproceedings":"CONF","phdthesis":"THES",
        "mastersthesis":"THES","techreport":"RPRT","incollection":"CHAP","misc":"GEN"}

def export_ris(entries: list[Entry]) -> str:
    lines = []
    for e in entries:
        lines.append(f"TY  - {_RIS.get(e.get('type','misc'),'GEN')}")
        if e.get("title"): lines.append(f"TI  - {e['title']}")
        for a in e.get("authors",[]): lines.append(f"AU  - {a}")
        for k,t in [("year","PY"),("journal","JO"),("booktitle","T2"),
                     ("volume","VL"),("number","IS"),("doi","DO"),("url","UR"),
                     ("isbn","SN"),("abstract","AB"),("publisher","PB")]:
            if e.get(k): lines.append(f"{t}  - {e[k]}")
        if e.get("pages"):
            sp, _, ep = e["pages"].partition("--")
            lines.append(f"SP  - {sp.strip()}")
            if ep: lines.append(f"EP  - {ep.strip()}")
        for t in e.get("tags",[]): lines.append(f"KW  - {t}")
        lines += ["ER  - ", ""]
    return "\n".join(lines)

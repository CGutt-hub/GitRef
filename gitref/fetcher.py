"""Fetch metadata (DOI/arXiv/ISBN) and download PDFs."""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
from http.client import HTTPResponse
from pathlib import Path
from typing import Any

_ARXIV_RE: re.Pattern[str] = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
_ISBN_RE: re.Pattern[str] = re.compile(r"(?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx]")
_HDR: dict[str, str] = {"User-Agent": "GitRef/0.1"}


def _get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> HTTPResponse:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers or _HDR), timeout=timeout)

# ── DOI (Crossref) ─────────────────────────────────────────────

def fetch_doi(doi: str) -> dict[str, Any]:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    with _get(url, {"Accept": "application/json"}) as r:
        d = json.loads(r.read().decode())["message"]
    authors = [f"{a.get('given','')} {a.get('family','')}".strip()
               for a in d.get("author", []) if a.get("family")]
    year = ""
    for k in ("published-print", "published-online", "created"):
        dp = d.get(k, {}).get("date-parts", [[]])
        if dp and dp[0]: year = str(dp[0][0]); break
    jn = d.get("container-title", [])
    return {"title": (d.get("title") or [""])[0], "authors": authors, "year": year,
            "doi": doi, "url": d.get("URL", ""), "abstract": d.get("abstract", ""),
            "journal": jn[0] if jn else "",
            "volume": d.get("volume", ""), "number": d.get("issue", ""),
            "pages": d.get("page", ""), "publisher": d.get("publisher", ""),
            "issn": (d.get("ISSN") or [""])[0], "isbn": (d.get("ISBN") or [""])[0]}

# ── arXiv ───────────────────────────────────────────────────────

def fetch_arxiv(arxiv_id: str) -> dict[str, Any]:
    aid = _ARXIV_RE.search(arxiv_id.strip().rstrip("/"))
    aid = aid.group(1) if aid else arxiv_id.strip()
    with _get(f"http://export.arxiv.org/api/query?id_list={aid}") as r:
        xml = r.read().decode()
    entry = re.search(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    x = entry.group(1) if entry else xml
    def t(tag):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", x, re.DOTALL)
        return m.group(1).strip() if m else ""
    pub = t("published")
    return {"title": t("title"), "authors": re.findall(r"<name>(.+?)</name>", x),
            "year": pub[:4] if pub else "", "arxiv_id": aid,
            "url": f"https://arxiv.org/abs/{aid}", "abstract": t("summary")}

# ── ISBN (Open Library) ─────────────────────────────────────────

def fetch_isbn(isbn: str) -> dict[str, Any]:
    isbn = re.sub(r"[-\s]", "", isbn)
    with _get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data") as r:
        data = json.loads(r.read().decode())
    key = f"ISBN:{isbn}"
    if key not in data:
        raise ValueError(f"ISBN {isbn} not found")
    b = data[key]
    authors = [a.get("name", "") for a in b.get("authors", [])]
    year = b.get("publish_date", "")
    m = re.search(r"(\d{4})", year)
    year = m.group(1) if m else year
    pubs = b.get("publishers", [])
    return {"title": b.get("title", ""), "authors": authors, "year": year,
            "isbn": isbn, "publisher": pubs[0].get("name","") if pubs else "",
            "url": b.get("url", ""), "pages": str(b.get("number_of_pages", ""))}

# ── PDF / snapshot download ─────────────────────────────────────

def _sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def download_pdf(url: str, dest_dir: str, filename: str | None = None) -> str:
    dest = Path(dest_dir) / "resources"; dest.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = url.split("/")[-1]
        if not filename.endswith(".pdf"): filename += ".pdf"
    filename = _sanitize(filename)
    (dest / filename).write_bytes(_get(url, timeout=60).read())
    return f"resources/{filename}"

def auto_download(meta: dict[str, Any], dest_dir: str) -> str:
    """Try to download PDF. Returns relative path or ''."""
    if meta.get("arxiv_id"):
        try: return download_pdf(f"https://arxiv.org/pdf/{meta['arxiv_id']}.pdf",
                                 dest_dir, f"{meta['arxiv_id']}.pdf")
        except Exception: pass
    if meta.get("doi"):
        try:
            with _get(f"https://doi.org/{meta['doi']}",
                       {"Accept": "application/pdf", **_HDR}, timeout=20) as r:
                if "pdf" in r.headers.get("Content-Type", ""):
                    safe = _sanitize(meta["doi"]) + ".pdf"
                    d = Path(dest_dir) / "resources"; d.mkdir(parents=True, exist_ok=True)
                    (d / safe).write_bytes(r.read())
                    return f"resources/{safe}"
        except Exception: pass
    return ""

# ── Identifier detection ───────────────────────────────────────

def detect_identifier(text: str) -> tuple[str, str] | None:
    """Returns (type, value) or None. Checks DOI, arXiv, ISBN."""
    doi = re.search(r"(10\.\d{4,}/[^\s]+)", text)
    if doi: return ("doi", doi.group(1).rstrip(".,;)"))
    arxiv = _ARXIV_RE.search(text)
    if arxiv: return ("arxiv", arxiv.group(1))
    isbn = _ISBN_RE.search(re.sub(r"[-\s]", "", text))
    if isbn: return ("isbn", isbn.group(0))
    return None

"""Generate resources/resources.md from .resources.bib.

This is the browsable reference list with clickable PDF links.
Run via `gitref watch` (auto) or triggered on every bib save.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .metadata import load, Entry


_LATEX_ACCENTS: dict[str, str] = {
    '`': '\u0300', "'": '\u0301', '^': '\u0302', '"': '\u0308',
    '~': '\u0303', '=': '\u0304', '.': '\u0307', 'u': '\u0306',
    'v': '\u030C', 'H': '\u030B', 'c': '\u0327', 'd': '\u0323',
    'b': '\u0332', 'k': '\u0328',
}
_LATEX_SPECIAL: dict[str, str] = {
    r'\ss': 'ß', r'\ae': 'æ', r'\oe': 'œ', r'\AA': 'Å',
    r'\o': 'ø', r'\O': 'Ø', r'\l': 'ł', r'\L': 'Ł',
}

def _decode_latex(s: str) -> str:
    """Best-effort conversion of LaTeX accents to Unicode."""
    import re, unicodedata
    for tex, char in _LATEX_SPECIAL.items():
        s = s.replace(tex, char)
    def _replace(m: re.Match) -> str:
        cmd, letter = m.group(1), m.group(2)
        comb = _LATEX_ACCENTS.get(cmd, '')
        if comb:
            return unicodedata.normalize('NFC', letter + comb)
        return letter
    s = re.sub(r"\{\\([`'^\"~=.uvHcdbk])\{(\w)\}\}", _replace, s)
    s = re.sub(r"\\([`'^\"~=.uvHcdbk])\{(\w)\}", _replace, s)
    s = re.sub(r"\{\\([`'^\"~=.uvHcdbk])(\w)\}", _replace, s)
    # Remove leftover braces
    s = s.replace('{', '').replace('}', '')
    return s


def _md_escape(s: str) -> str:
    """Escape pipe characters for markdown tables."""
    return _decode_latex(s).replace("|", "\\|").replace("\n", " ").strip()


def build_table(entries: list[Entry], relative_pdf: bool = False,
                local_pdfs: set[str] | None = None) -> str:
    lines: list[str] = []
    lines.append("| # | Key | Year | Authors | Title | Type | PDF | Links |")
    lines.append("|--:|-----|------|---------|-------|------|:---:|-------|")
    for i, e in enumerate(sorted(entries, key=lambda x: x.get("year", ""), reverse=True), 1):
        auth = ", ".join(e.get("authors", [])[:3])
        if len(e.get("authors", [])) > 3:
            auth += " et al."
        auth = _md_escape(auth)
        title = _md_escape(e.get("title", ""))
        links: list[str] = []
        if e.get("doi"):
            links.append(f"[DOI](https://doi.org/{e['doi']})")
        if e.get("arxiv_id"):
            links.append(f"[arXiv](https://arxiv.org/abs/{e['arxiv_id']})")
        if e.get("url") and not e.get("doi") and not e.get("arxiv_id"):
            links.append(f"[URL]({e['url']})")
        if e.get("isbn"):
            links.append(f"ISBN:{e['isbn']}")
        # PDF status column
        pdf_status = "—"
        if e.get("pdf"):
            fname = e["pdf"].split("/")[-1]
            if local_pdfs is not None:
                pdf_status = "✅" if fname in local_pdfs else "❌"
            else:
                pdf_status = "📎"
            if relative_pdf:
                links.append(f"[PDF]({fname})")
            else:
                links.append(f"`{fname}`")
        etype = e.get("type", "misc")
        key = e.get("key", "")
        year = e.get("year", "")
        lines.append(f"| {i} | `{key}` | {year} | {auth} | {title} | {etype} | {pdf_status} | {' · '.join(links)} |")
    return "\n".join(lines)


def build_collections(entries: list[Entry]) -> str:
    tags: dict[str, list[str]] = {}
    for e in entries:
        for t in e.get("tags", []):
            tags.setdefault(t, []).append(e.get("key", ""))
    if not tags:
        return ""
    lines = ["\n### Collections\n"]
    for tag in sorted(tags):
        keys = ", ".join(f"`{k}`" for k in tags[tag])
        lines.append(f"- **{tag}** — {keys}")
    return "\n".join(lines)


def build_details(entries: list[Entry]) -> str:
    """Build collapsible abstract sections per entry."""
    blocks: list[str] = []
    for e in sorted(entries, key=lambda x: x.get("year", ""), reverse=True):
        abstract = e.get("abstract", "").strip()
        if not abstract:
            continue
        key = e.get("key", "")
        title = e.get("title", "No title")
        year = e.get("year", "")
        auth = ", ".join(e.get("authors", [])[:3])
        if len(e.get("authors", [])) > 3:
            auth += " et al."
        blocks.append(
            f"<details>\n"
            f"<summary><strong>{key}</strong> — {title} ({year})</summary>\n\n"
            f"**Authors:** {auth}  \n"
            f"**Abstract:** {abstract}\n\n"
            f"</details>"
        )
    if not blocks:
        return ""
    return "\n### Abstracts\n\n" + "\n\n".join(blocks)


def build_stats(entries: list[Entry], local_pdfs: set[str] | None = None) -> str:
    types: dict[str, int] = {}
    for e in entries:
        t = e.get("type", "misc")
        types[t] = types.get(t, 0) + 1
    parts = [f"{n} {t}{'s' if n > 1 else ''}" for t, n in sorted(types.items())]
    has_pdf = [e for e in entries if e.get("pdf")]
    if local_pdfs is not None:
        present = sum(1 for e in has_pdf if e["pdf"].split("/")[-1] in local_pdfs)
        missing = len(has_pdf) - present
        pdf_info = f"**{present}** PDFs local · **{missing}** missing"
    else:
        pdf_info = f"**{len(has_pdf)}** files attached"
    return f"**{len(entries)}** references ({', '.join(parts)}) · {pdf_info}"


def _get_local_pdfs(repo: Path) -> set[str]:
    """Return set of PDF filenames that are locally available (loose or in zip)."""
    import zipfile
    res = repo / "resources"
    local: set[str] = set()
    # Loose PDFs
    for f in res.glob("*.pdf"):
        local.add(f.name)
    # PDFs in zip
    zp = res / ".resources.zip"
    if zp.exists():
        try:
            with zipfile.ZipFile(str(zp)) as zf:
                local.update(zf.namelist())
        except Exception:
            pass
    return local


def update_readme(repo_path: str) -> int:
    """Regenerate resources/resources.md from the bib file."""
    repo = Path(repo_path)
    entries = load(str(repo))

    res_md = repo / "resources" / "resources.md"
    res_md.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        res_content = "# Resources\n\n*Library is empty.*\n"
    else:
        local_pdfs = _get_local_pdfs(repo)
        res_content = "\n".join([
            "# Resources",
            "",
            build_stats(entries, local_pdfs),
            "",
            "> **Tip:** Run `gitref watch` to extract all PDFs — then click the 📎 links below to open them.",
            "",
            build_table(entries, relative_pdf=True, local_pdfs=local_pdfs),
            build_details(entries),
            build_collections(entries),
            "",
            f"*Auto-generated from `.resources.bib` — {len(entries)} entries.*",
            "",
        ])
    res_md.write_text(res_content, encoding="utf-8")

    return len(entries)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    n = update_readme(path)
    print(f"resources.md updated with {n} entries.")

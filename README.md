# GitRef

A git-based reference manager — like Zotero, but your library is a plain git repo.

## Install

### Download (recommended)

Grab the latest release from the [**Releases page**](https://github.com/CGutt-hub/gitref/releases/latest):

| Platform | Download |
|----------|----------|
| **Windows** | [`gitref.exe`](https://github.com/CGutt-hub/gitref/releases/latest/download/gitref.exe) |
| **Linux (AppImage)** | [`GitRef-x86_64.AppImage`](https://github.com/CGutt-hub/gitref/releases/latest/download/GitRef-x86_64.AppImage) |
| **Linux (binary)** | [`gitref`](https://github.com/CGutt-hub/gitref/releases/latest/download/gitref) |

**Windows:** Move `gitref.exe` somewhere on your PATH (e.g. `C:\Users\<you>\AppData\Local\GitRef\`), or run the installer:
```powershell
irm https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.ps1 | iex
```

**Linux:** Make the AppImage executable and move it:
```bash
chmod +x GitRef-x86_64.AppImage
sudo mv GitRef-x86_64.AppImage /usr/local/bin/gitref
```
Or use the one-liner:
```bash
curl -fsSL https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.sh | bash
```

### From source (pip)

```bash
pip install git+https://github.com/CGutt-hub/gitref.git
```

## Features

- **DOI / arXiv / ISBN lookup** – paste an identifier, metadata is fetched automatically
- **PDF download** – auto-downloads from arXiv or DOI resolvers
- **BibTeX store** – all references in `.resources.bib` (human-readable, diffable, standard)
- **Zip archive** – PDFs stored compactly in `.resources.zip` for git efficiency
- **File watcher** – `gitref watch` extracts all PDFs, auto-adds dropped files, auto-repacks on close
- **Clickable links** – `resources.md` has direct PDF links when watcher is running
- **Git sync** – auto-commit + pull + push to keep your library in sync across machines
- **Terminal UI** – interactive browser with search, detail view, tagging
- **Browser bookmarklet** – one-click save from any paper page

## Quick start

```bash
# Initialise a new library
gitref init

# Add a paper by DOI
gitref add "10.1038/s41586-024-07487-w"

# Add by arXiv ID
gitref add "2401.12345"

# Start watcher (extracts PDFs, watches for new/modified files)
gitref watch

# Open interactive TUI
gitref browse

# Sync with remote
gitref sync
```

## Workflow

**DAU-friendly PDF access** — no need to use `gitref open` / `gitref close`:

1. Run `gitref watch` — this extracts all PDFs from the archive
2. Open `resources/resources.md` and click any 📎 link to read a paper
3. Drop a PDF into `resources/` and it's auto-added to the library
4. Close your PDF viewer (or just hit Ctrl+C on the watcher) — files are repacked

## Browser bookmarklet

1. Start the local server:
   ```bash
   gitref serve
   ```
2. Create a new bookmark in your browser with this URL:
   ```
   javascript:(function(){var u=window.location.href,t=document.title,d=document.querySelector('meta[name="citation_doi"]')||document.querySelector('meta[name="dc.identifier"]');if(d){var v=d.getAttribute("content");if(v&&v.match(/^10\./))u="https://doi.org/"+v}fetch("http://127.0.0.1:7342/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:u,title:t})}).then(r=>r.json()).then(d=>{var e=document.createElement("div");e.textContent="GitRef: saved — "+d.title;e.style.cssText="position:fixed;top:10px;right:10px;z-index:999999;padding:12px 20px;border-radius:8px;font:14px/1.4 sans-serif;color:#fff;background:#2ea043;box-shadow:0 2px 8px rgba(0,0,0,.3)";document.body.appendChild(e);setTimeout(()=>e.remove(),3000)}).catch(()=>{var e=document.createElement("div");e.textContent="GitRef: failed — is gitref serve running?";e.style.cssText="position:fixed;top:10px;right:10px;z-index:999999;padding:12px 20px;border-radius:8px;font:14px/1.4 sans-serif;color:#fff;background:#d73a49;box-shadow:0 2px 8px rgba(0,0,0,.3)";document.body.appendChild(e);setTimeout(()=>e.remove(),3000)})})()
   ```
3. Navigate to any paper page and click the bookmarklet — the reference is saved to your library.

## Library structure

```
~/GitRef/
├── .git/
├── .github/workflows/      # auto-regenerates resources.md on push
├── README.md
└── resources/
    ├── .resources.bib       # BibTeX metadata (source of truth)
    ├── .resources.zip       # all PDFs, compressed
    └── resources.md         # browsable table with clickable PDF links
```

## Commands

Run `gitref --help` for full usage. Key commands:

| Command | Description |
|---------|-------------|
| `gitref init` | Create a new library (git repo + bib) |
| `gitref add <id>` | Add by DOI, arXiv ID, ISBN, or URL |
| `gitref search <q>` | Search title, authors, tags |
| `gitref list` | Print all entries |
| `gitref browse` | Interactive TUI |
| `gitref watch` | Extract all PDFs, auto-add/repack on changes |
| `gitref open <key>` | Extract a single PDF for reading |
| `gitref close <key>` | Repack a PDF into archive |
| `gitref compact` | Pack all loose PDFs into archive |
| `gitref sync` | Git add + commit + pull + push |
| `gitref serve` | Start bookmarklet server (port 7342) |
| `gitref export` | Export library as RIS |

Use `-l <path>` to specify a custom library location (default: `~/GitRef`).

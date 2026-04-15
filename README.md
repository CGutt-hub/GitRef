# GitRef

A git-based reference manager — like Zotero, but your library is a plain git repo.

## Install

### pip (recommended)

```bash
pip install gitref
```

### Standalone binary

Download from the [**Releases page**](https://github.com/CGutt-hub/gitref/releases/latest):

| Platform | Asset | Install |
|----------|-------|---------|
| **Windows** | `gitref.exe` | Move to a folder on your PATH, or run: `irm https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.ps1 \| iex` |
| **Linux** | `GitRef-x86_64.AppImage` or `gitref` | `chmod +x` and move to `/usr/local/bin/`, or run: `curl -fsSL https://raw.githubusercontent.com/CGutt-hub/gitref/main/install.sh \| bash` |

### From source

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
- **Browser extension** – one-click save from any paper page (like Zotero Connector)

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

## Browser extension

GitRef includes a Chrome/Edge extension (Manifest V3) that works like the Zotero Connector — click the toolbar icon on any paper page to save it to your library.

### Setup

1. Start the local server:
   ```bash
   gitref serve
   ```
2. Load the extension:
   - Open `chrome://extensions` (or `edge://extensions`)
   - Enable **Developer mode**
   - Click **Load unpacked** and select the `extension/` folder from this repo
3. Navigate to any paper page and click the GitRef icon — the reference (and PDF if available) is saved automatically.

The extension auto-detects DOIs, arXiv IDs, and citation metadata from the page, just like Zotero Connector.

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
| `gitref serve` | Start server for browser extension (port 7342) |
| `gitref export` | Export library as RIS |

Use `-l <path>` to specify a custom library location (default: `~/GitRef`).

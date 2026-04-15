"""Git repository management: init, commit, push, pull."""

import shutil
import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


_TEMPLATES = Path(__file__).resolve().parent / "templates"


def init_repo(path: str) -> Path:
    """Initialise a new GitRef library at *path* (creates dir + git init)."""
    repo = Path(path).resolve()
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        _run_git(["init"], str(repo))
    # Ensure resources folder and bib file exist
    (repo / "resources").mkdir(exist_ok=True)
    bib = repo / "resources" / ".resources.bib"
    if not bib.exists():
        bib.write_text("", encoding="utf-8")
    # Install GitHub Action workflow
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    src = _TEMPLATES / "update-readme.yml"
    if src.exists() and not (wf / "update-readme.yml").exists():
        shutil.copy2(str(src), str(wf / "update-readme.yml"))
    # Seed README
    readme = repo / "README.md"
    if not readme.exists():
        readme.write_text(
            "# References\n\nManaged by [GitRef](https://github.com/guttlein/GitRef).\n"
            "Browse the library in [`resources/resources.md`](resources/resources.md).\n",
            encoding="utf-8",
        )
    _run_git(["add", "-A"], str(repo))
    status = _run_git(["status", "--porcelain"], str(repo))
    if status.stdout.strip():
        _run_git(["commit", "-m", "init: empty library"], str(repo))
    return repo


def sync(repo: str, message: str = "gitref: auto-sync") -> str:
    """Reconcile stale refs, stage all changes, commit, pull --rebase, push."""
    from . import metadata
    cwd = str(Path(repo).resolve())

    # Clean up file refs for deleted PDFs before committing
    cleaned = metadata.reconcile(cwd)
    # Auto-pack all loose PDFs into archive
    packed = metadata.pack_all(cwd)
    _run_git(["add", "-A"], cwd)

    # Only commit if there are staged changes
    status = _run_git(["status", "--porcelain"], cwd)
    if status.stdout.strip():
        _run_git(["commit", "-m", message], cwd)

    # Pull with rebase to avoid merge commits, then push
    pull = _run_git(["pull", "--rebase"], cwd)
    push = _run_git(["push"], cwd)

    parts = []
    if cleaned:
        parts.append(f"reconciled {cleaned} stale ref(s)")
    if packed:
        parts.append(f"packed {packed} PDF(s)")
    if status.stdout.strip():
        parts.append("committed")
    if pull.returncode == 0 and "up to date" not in pull.stdout:
        parts.append("pulled")
    if push.returncode == 0:
        parts.append("pushed")
    return ", ".join(parts) if parts else "nothing to sync"


def has_remote(repo: str) -> bool:
    r = _run_git(["remote"], str(Path(repo).resolve()))
    return bool(r.stdout.strip())

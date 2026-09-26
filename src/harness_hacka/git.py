"""O pouco de git que o harness usa. Tudo degrada para "sem git" sem levantar erro."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path


def _git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def last_changed(root: Path, folder: Path) -> dict[str, date]:
    """Data do último commit que tocou cada arquivo da pasta. Uma chamada só ao git."""
    # --relative: caminhos relativos à raiz do projeto, mesmo quando ela não é a raiz do repo.
    out = _git(root, "log", "--relative", "--format=@@%cs", "--name-only", "--", folder.as_posix())
    if out is None:
        return {}
    dates: dict[str, date] = {}
    current: date | None = None
    for line in out.splitlines():
        if line.startswith("@@"):
            try:
                current = date.fromisoformat(line[2:].strip())
            except ValueError:
                current = None
        elif line.strip() and current is not None:
            dates.setdefault(line.strip(), current)
    return dates


def commits_since(root: Path, moment: datetime | None) -> list[dict[str, str]]:
    """Commits que tocaram o projeto depois de `moment`, do mais novo para o mais velho.

    `-- .` limita à pasta do projeto: num monorepo, o commit de outro projeto não conta.
    """
    args = ["log", "--format=%h%x09%an%x09%cs%x09%s", "-n", "200"]
    if moment is not None:
        args.append(f"--since={moment.isoformat(timespec='minutes')}")
    out = _git(root, *args, "--", ".")
    if not out:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("\t", 3)
        if len(parts) == 4:
            commits.append(dict(zip(("hash", "author", "date", "subject"), parts, strict=True)))
    return commits


def user_name(root: Path) -> str:
    return (_git(root, "config", "user.name") or "").strip()


def is_tracked(root: Path, path: Path) -> bool:
    return _git(root, "ls-files", "--error-unmatch", path.as_posix()) is not None


def add(root: Path, path: Path) -> None:
    _git(root, "add", "--", path.as_posix())


def move(root: Path, source: Path, target: Path) -> None:
    """`git mv` quando o arquivo está no git (preserva o histórico); senão, move no disco."""
    target.parent.mkdir(parents=True, exist_ok=True)
    rel_source = source.relative_to(root).as_posix()
    rel_target = target.relative_to(root).as_posix()
    tracked = is_tracked(root, source.relative_to(root))
    # `_git` devolve "" quando dá certo: comparar com None, não com verdadeiro.
    if tracked and _git(root, "mv", rel_source, rel_target) is not None:
        return
    shutil.move(str(source), str(target))

"""Fixtures sintéticas. Nenhum teste depende de um repositório real: teste que quebra porque
outro projeto mudou é teste que o time aprende a ignorar."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from harness_hacka import config
from harness_hacka.memory import Memory, load

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "bin" / "harness-hacka.py"


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8", newline="\n")
    return path


def cfg_of(root: Path) -> config.Config:
    cfg = config.load(root)
    assert cfg is not None
    return cfg


def memory_of(root: Path) -> Memory:
    return load(cfg_of(root))


@pytest.fixture(autouse=True)
def isolated_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Estado de sessão (aprovações, avisos) numa pasta só deste teste."""
    folder = tmp_path / "tmp"
    folder.mkdir()
    for var in ("TMPDIR", "TEMP", "TMP"):
        monkeypatch.setenv(var, str(folder))
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    write(root, ".claude/harness-hacka.json", json.dumps({"project": "Teste"}))
    (root / "memory").mkdir()
    return root


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def git_project(project: Path) -> Path:
    git(project, "init", "-q")
    git(project, "config", "user.name", "Pessoa Teste")
    git(project, "config", "user.email", "teste@exemplo.com")
    git(project, "config", "core.autocrlf", "false")
    return project


def run_hook(name: str, event: dict, root: Path, tmp: Path) -> subprocess.CompletedProcess[str]:
    """Roda o hook do jeito que o Claude Code roda: processo novo, evento no stdin."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root), "TMPDIR": str(tmp)}
    env["TEMP"] = env["TMP"] = str(tmp)
    return subprocess.run(
        [sys.executable, str(LAUNCHER), "hook", name],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
        check=False,
    )


NOTE = """
    ---
    read_when: antes de mexer no banco
    review_by: 2999-01-01
    ---
    # Banco

    Usamos Supabase na nuvem.
    """

DECISION = """
    ---
    status: {status}
    date: 2026-09-20
    decided_by: {owner}
    supersedes: [{supersedes}]
    superseded_by: [{superseded_by}]
    ---

    # {number}: {title}

    ## Rule

    - {rule}

    ## Context

    Texto.
    """


def decision(
    root: Path,
    number: int,
    title: str = "Uma decisao",
    status: str = "accepted",
    owner: str = "Pessoa",
    supersedes: str = "",
    superseded_by: str = "",
    rule: str = "Faça assim.",
) -> Path:
    text = (
        textwrap.dedent(DECISION)
        .lstrip("\n")
        .format(
            status=status,
            owner=owner,
            supersedes=supersedes,
            superseded_by=superseded_by,
            number=f"{number:04d}",
            title=title,
            rule=rule,
        )
    )
    slug = title.lower().replace(" ", "-")
    return write(root, f"memory/decisions/{number:04d}-{slug}.md", text)


ENTRY = """
    ---
    author: Pessoa
    status: partial
    ---

    # {title}

    ## Changes

    - Coisa feita.

    ## Dead ends

    {dead_ends}

    ## Verification

    - 3 testes passando.

    ## Next steps

    - [ ] Próxima coisa.
    """


def entry(root: Path, name: str, title: str = "Sessão", dead_ends: str = "- none") -> Path:
    text = textwrap.dedent(ENTRY).lstrip("\n").format(title=title, dead_ends=dead_ends)
    return write(root, f"memory/journal/{name}.md", text)

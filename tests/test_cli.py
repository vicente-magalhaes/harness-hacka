"""O CLI de ponta a ponta: init, new, archive, index e check."""

from __future__ import annotations

import json
import subprocess

import pytest

from harness_hacka.cli import main

from .conftest import NOTE, decision, git, write


def run(capsys, *args):
    code = main(list(args))
    return code, capsys.readouterr().out


def test_init_is_born_passing_and_never_overwrites(tmp_path, capsys):
    root = tmp_path / "novo"
    root.mkdir()
    code, out = run(capsys, "--project", str(root), "init", "--profile", "nextjs")
    assert code == 0 and "criado: .claude/harness-hacka.json" in out
    assert (
        json.loads((root / ".claude/harness-hacka.json").read_text(encoding="utf-8"))["profile"]
        == "nextjs"
    )
    assert run(capsys, "--project", str(root), "check")[0] == 0

    (root / "memory/README.md").write_text("# meu README\n", encoding="utf-8")
    _, out = run(capsys, "--project", str(root), "init")
    assert "nada a criar" in out
    assert (root / "memory/README.md").read_text(encoding="utf-8") == "# meu README\n"


def test_init_with_custom_memory_dir_writes_it_to_the_config(tmp_path, capsys):
    root = tmp_path / "br"
    root.mkdir()
    run(capsys, "--project", str(root), "init", "--profile", "python", "--memory-dir", "memoria")
    cfg = json.loads((root / ".claude/harness-hacka.json").read_text(encoding="utf-8"))
    assert cfg["memory_dir"] == "memoria"
    assert (root / "memoria/decisions/README.md").is_file()
    assert run(capsys, "--project", str(root), "check")[0] == 0


def test_init_with_unknown_profile_fails(tmp_path):
    with pytest.raises(SystemExit, match="não existe"):
        main(["--project", str(tmp_path), "init", "--profile", "cobol"])


def test_check_without_config_fails(tmp_path):
    with pytest.raises(SystemExit, match="não adotou"):
        main(["--project", str(tmp_path), "check"])


def test_new_numbers_and_names(project, capsys):
    decision(project, 3)
    _, out = run(
        capsys, "--project", str(project), "new", "decision", "Busca por similaridade com pgvector"
    )
    assert out.strip() == "memory/decisions/0004-busca-por-similaridade-com-pgvector.md"
    _, out = run(
        capsys, "--project", str(project), "new", "journal", "Tela de publicação", "--author", "Ana"
    )
    path = project / out.strip()
    assert path.parent.name == "journal" and path.name.endswith("-tela-de-publicacao.md")
    assert "author: Ana" in path.read_text(encoding="utf-8")


def test_fresh_entry_fails_until_filled(project, capsys):
    run(capsys, "--project", str(project), "new", "journal", "Rascunho")
    code, out = run(capsys, "--project", str(project), "check")
    assert code == 1 and "unfilled-template" in out


def test_archive_moves_with_git_and_records_the_reason(git_project, capsys):
    write(git_project, "memory/velha.md", NOTE)
    git(git_project, "add", "-A")
    git(git_project, "commit", "-qm", "inicio")
    _, out = run(
        capsys,
        "--project",
        str(git_project),
        "archive",
        "memory/velha.md",
        "--reason",
        "virou decisão 0001",
    )
    assert out.strip() == "memory/archive/velha.md"
    text = (git_project / "memory/archive/velha.md").read_text(encoding="utf-8")
    assert "archived_at:" in text and 'reason: "virou decisão 0001"' in text
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_project, capture_output=True, text=True
    ).stdout
    assert "R  memory/velha.md -> memory/archive/velha.md" in status


@pytest.mark.parametrize(
    "target", ["memory/decisions/0001-uma-decisao.md", "README.md", "memory/nao-existe.md"]
)
def test_archive_refuses(project, target):
    decision(project, 1)
    write(project, "README.md", "# fora da memória\n")
    with pytest.raises(SystemExit):
        main(["--project", str(project), "archive", target, "--reason", "x"])


def test_status_json_lists_candidates(project, capsys):
    write(project, "memory/velha.md", "---\nread_when: x\nreview_by: 2020-01-01\n---\n# V\n")
    _, out = run(capsys, "--project", str(project), "status", "--json")
    data = json.loads(out)
    assert data["housekeeping"]["candidates"][0]["path"] == "memory/velha.md"
    assert data["housekeeping"]["last_run"] is None


def test_index_update_is_idempotent(project, capsys):
    write(project, "memory/banco.md", NOTE)
    write(project, "CLAUDE.md", "<!-- harness-hacka:index -->\n<!-- /harness-hacka:index -->\n")
    assert "atualizado: CLAUDE.md" in run(capsys, "--project", str(project), "index", "--update")[1]
    assert "índices em dia" in run(capsys, "--project", str(project), "index", "--update")[1]


def test_index_keeps_crlf(project, capsys):
    write(project, "memory/banco.md", NOTE)
    (project / "CLAUDE.md").write_bytes(
        b"# P\r\n<!-- harness-hacka:index -->\r\n<!-- /harness-hacka:index -->\r\n"
    )
    run(capsys, "--project", str(project), "index", "--update")
    raw = (project / "CLAUDE.md").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")

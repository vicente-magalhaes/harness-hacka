"""A auditoria: o que reprova, o que só avisa, e o que não pode dar falso positivo."""

from __future__ import annotations

from datetime import date

from harness_hacka.checks import audit

from .conftest import NOTE, decision, entry, memory_of, write

TODAY = date(2026, 9, 26)


def codes(root, level=None, changed=None):
    return {
        f.code for f in audit(memory_of(root), TODAY, changed or {}) if level in (None, f.level)
    }


def test_minimal_memory_passes(project):
    write(project, "memory/banco.md", NOTE)
    assert codes(project, "error") == set()


def test_note_without_read_when_fails(project):
    write(project, "memory/solta.md", "# Sem frontmatter\n")
    assert "missing-read-when" in codes(project, "error")


def test_broken_frontmatter_fails(project):
    write(project, "memory/quebrada.md", "---\nread_when: x\n# nunca fecha\n")
    assert "frontmatter" in codes(project, "error")


def test_stale_by_review_by_today_or_past_and_by_git_age(project):
    write(project, "memory/velha.md", "---\nread_when: x\nreview_by: 2026-09-01\n---\n# V\n")
    write(project, "memory/hoje.md", "---\nread_when: x\nreview_by: 2026-09-26\n---\n# H\n")
    write(project, "memory/antiga.md", "---\nread_when: x\n---\n# A\n")
    findings = audit(memory_of(project), TODAY, {"memory/antiga.md": date(2026, 1, 1)})
    stale = {f.file for f in findings if f.code == "stale"}
    assert stale == {"memory/velha.md", "memory/hoje.md", "memory/antiga.md"}
    assert all(f.level == "warning" for f in findings if f.code == "stale")


def test_accepted_without_owner_fails(project):
    decision(project, 1, owner="")
    assert "decision-owner" in codes(project, "error")


def test_portuguese_status_is_normalized(project):
    decision(project, 1, status="aceita")
    assert "decision-status" not in codes(project)


def test_invalid_status_fails(project):
    decision(project, 1, status="maybe")
    assert "decision-status" in codes(project, "error")


def test_duplicate_number_fails(project):
    decision(project, 1, title="Uma")
    decision(project, 1, title="Outra")
    assert "decision-duplicate" in codes(project, "error")


def test_supersession_needs_both_sides(project):
    decision(project, 1, title="Antiga", status="accepted")
    decision(project, 2, title="Nova", status="accepted", supersedes="0001")
    assert "supersession" in codes(project, "error")


def test_complete_supersession_passes(project):
    decision(project, 1, title="Antiga", status="superseded", superseded_by="0002")
    decision(project, 2, title="Nova", status="accepted", supersedes="0001")
    assert "supersession" not in codes(project)


def test_superseded_by_a_proposal_is_not_valid(project):
    decision(project, 1, title="Antiga", status="superseded", superseded_by="0002")
    decision(project, 2, title="Nova", status="proposed", supersedes="0001")
    assert "supersession" in codes(project, "error")


def test_waiting_proposal_warns(project):
    decision(project, 1, status="proposed", owner="")  # data da fixture: 2026-09-20
    assert "proposal-waiting" in codes(project, "warning")


def test_broken_link_in_claude_md_fails(project):
    write(project, "CLAUDE.md", "Leia [a nota](memory/sumiu.md) e [o README](README.md).\n")
    write(project, "README.md", "# ok\n")
    found = [f for f in audit(memory_of(project), TODAY, {}) if f.code == "broken-link"]
    assert [(f.file, f.line) for f in found] == [("CLAUDE.md", 1)]


def test_dead_decision_reference_fails_without_caveat(project):
    decision(project, 1, title="Antiga", status="superseded", superseded_by="0002")
    decision(project, 2, title="Nova", status="accepted", supersedes="0001")
    write(
        project,
        "memory/nota.md",
        "---\nread_when: x\n---\n# N\n\nSiga a ADR-0001.\nA ADR-0001 foi substituída pela 0002.\n",
    )
    found = [f for f in audit(memory_of(project), TODAY, {}) if f.code == "dead-reference"]
    assert [f.line for f in found] == [6]  # linha do arquivo, contando o frontmatter


def test_outdated_index_fails_and_updated_passes(project):
    from harness_hacka import index

    write(project, "memory/banco.md", NOTE)
    write(
        project, "CLAUDE.md", "# P\n\n<!-- harness-hacka:index -->\n<!-- /harness-hacka:index -->\n"
    )
    assert "outdated-index" in codes(project, "error")
    index.update(memory_of(project))
    assert "outdated-index" not in codes(project)
    text = (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert "[memory/banco.md](memory/banco.md) | Banco | antes de mexer no banco |" in text


def test_secret_in_memory_fails_even_in_the_archive(project):
    key = "sk-ant-api03-" + "A" * 30
    write(project, "memory/archive/velho.md", f"# Velho\n\nchave: {key}\n")
    assert "secret" in codes(project, "error")


def test_variable_name_is_not_a_secret(project):
    write(
        project,
        "memory/banco.md",
        "---\nread_when: x\n---\n# B\n\nA chave fica em `SUPABASE_SECRET_KEY`. senha: pedir.\n",
    )
    assert "secret" not in codes(project)


def test_cpf_warns(project):
    write(project, "memory/x.md", "---\nread_when: x\n---\n# X\n\nCPF 123.456.789-00\n")
    assert "personal-data" in codes(project, "warning")


def test_entry_without_sections_and_bad_name_fails(project):
    write(project, "memory/journal/sessao-sem-data.md", "---\nstatus: partial\n---\n# S\n")
    assert {"entry-filename", "entry-sections"} <= codes(project, "error")


def test_complete_entry_passes_and_old_one_goes_to_triage(project):
    entry(project, "2026-09-10-1400-sessao-velha")
    entry(project, "2026-09-26-0900-sessao-nova")
    findings = audit(memory_of(project), TODAY, {})
    assert not [f for f in findings if f.level == "error"]
    triage = [f.file for f in findings if f.code == "journal-triage"]
    assert triage == ["memory/journal/2026-09-10-1400-sessao-velha.md"]


def test_portuguese_entry_status_is_normalized(project):
    path = entry(project, "2026-09-26-0900-sessao")
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: partial", "status: parcial"),
        encoding="utf-8",
    )
    assert "entry-status" not in codes(project)


def test_unfilled_template_fails_with_the_right_line(project):
    path = entry(project, "2026-09-26-0900-rascunho")
    text = path.read_text(encoding="utf-8").replace(
        "- Coisa feita.", "- {mudança concreta e verificável}"
    )
    path.write_text(text, encoding="utf-8")
    found = [f for f in audit(memory_of(project), TODAY, {}) if f.code == "unfilled-template"]
    line = text.splitlines().index("- {mudança concreta e verificável}") + 1
    assert [(f.level, f.line) for f in found] == [("error", line)]

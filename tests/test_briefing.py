"""O bloco do início de sessão: o que entra, e como ele encolhe sem mentir."""

from __future__ import annotations

import json
from datetime import date

from harness_hacka import briefing

from .conftest import NOTE, decision, entry, memory_of, write

TODAY = date(2026, 9, 26)


def test_shows_decisions_last_session_and_lessons(project):
    decision(project, 1, title="Supabase na nuvem", rule="Estrutura só por migração.")
    decision(project, 2, title="Nome do produto", status="proposed", owner="")
    entry(
        project,
        "2026-09-26-1000-sessao",
        dead_ends="- Supabase local → falhou porque o time é Windows. **Lesson:** use a nuvem",
    )
    text = briefing.build(memory_of(project), TODAY)
    assert "0001 Supabase na nuvem (accepted, Pessoa). Regra: Estrutura só por migração." in text
    assert "0002 Nome do produto (proposed: ainda não vale)." in text
    assert "responda `accept 0002`" in text
    assert "**Lesson:** use a nuvem" in text
    assert "- [ ] Próxima coisa." in text


def test_notes_index_only_when_claude_md_lacks_it(project):
    write(project, "memory/banco.md", NOTE)
    assert "`memory/banco.md`: ler quando antes de mexer no banco" in briefing.build(
        memory_of(project), TODAY
    )
    write(project, "CLAUDE.md", "<!-- harness-hacka:index -->\n<!-- /harness-hacka:index -->\n")
    assert "### Notas" not in briefing.build(memory_of(project), TODAY)


def test_dead_decision_only_as_a_count(project):
    decision(project, 1, title="Antiga", status="superseded", superseded_by="0002")
    decision(project, 2, title="Nova", supersedes="0001")
    text = briefing.build(memory_of(project), TODAY)
    assert "Antiga" not in text
    assert "+1 superseded, deprecated ou rejected" in text


def test_budget_cuts_in_order_and_says_so(project):
    write(project, ".claude/harness-hacka.json", json.dumps({"briefing": {"max_chars": 1500}}))
    for i in range(1, 30):
        write(
            project,
            f"memory/nota-{i:02d}.md",
            f"---\nread_when: caso {i} " + "x" * 60 + "\n---\n# N\n",
        )
    for day in range(20, 27):  # sete sessões, a mais nova no dia 26
        dead_ends = "\n".join(
            f"- abordagem {day}.{i} → falhou. **Lesson:** lição {day}.{i}" for i in range(6)
        )
        entry(project, f"2026-09-{day}-1000-sessao", dead_ends=dead_ends)
    text = briefing.build(memory_of(project), TODAY)
    assert len(text) <= 1500
    assert "Notas: omitido por tamanho" in text  # o índice sai primeiro, e diz onde está
    assert "mais antigas em" in text  # as lições encolhem avisando quantas faltam
    assert "lição 26.0" in text  # as da sessão mais nova ficam
    assert "lição 20.0" not in text  # as da mais velha saem primeiro


def test_subagent_version_has_no_pending_nor_session(project):
    decision(project, 1, title="Supabase na nuvem")
    entry(project, "2026-09-26-1000-sessao")
    text = briefing.build(memory_of(project), TODAY, subagent=True)
    assert "0001 Supabase na nuvem" in text
    assert "Última sessão" not in text
    assert "Pendências" not in text


def test_empty_memory_does_not_break(project):
    assert briefing.build(memory_of(project), TODAY).startswith(
        "## Memória do projeto (harness-hacka)"
    )

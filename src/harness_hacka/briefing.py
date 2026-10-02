"""O bloco que o hook de início de sessão injeta no contexto.

Tem orçamento (`briefing.max_chars`, 6.000 por padrão). Acima de ~10.000 chars a plataforma
troca o bloco inteiro por uma prévia truncada (medido no harness-memoria), então o corte é
feito aqui, em ordem, e sempre avisado. Cortar calado apaga o único sinal de que falta algo.

Ordem de corte, do mais barato ao mais caro: índice de notas (já está no AGENTS.md, no
CLAUDE.md ou em memory/README.md), lições mais antigas, texto das regras, próximos passos,
lições, decisões.
Cabeçalho e pendências nunca saem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import git, index
from .checks import audit, stale_reason
from .memory import Memory, count_markers, plural

SUBAGENT_MAX_CHARS = 3000


@dataclass
class _Block:
    title: str
    lines: list[str] = field(default_factory=list)
    compact: list[str] | None = None
    pointer: str = ""
    mode: str = "full"  # full, compact, hidden

    def render(self) -> list[str]:
        if self.mode == "hidden":
            return (
                [f"{self.title}: omitido por tamanho. Ver {self.pointer}."] if self.pointer else []
            )
        body = self.compact if self.mode == "compact" and self.compact is not None else self.lines
        return [f"### {self.title}", *body] if body else []


def _pending(
    memory: Memory, today: date, changed: dict[str, date], commits: int, errors: int
) -> list[str]:
    cfg = memory.cfg
    lines = []
    proposals = [d for d in memory.decisions if d.status == "proposed"]
    for d in proposals[:3]:
        age = ""
        if d.decision_date and (today - d.decision_date).days > 0:
            age = f" há {plural((today - d.decision_date).days, 'dia', 'dias')}"
        lines.append(
            f"- A decisão {d.number:04d} está proposed{age}. Só uma pessoa aceita: mostre o "
            f"resumo e peça que ela responda `accept {d.number:04d}`."
        )
    if len(proposals) > 3:
        lines.append(f"- (+{len(proposals) - 3} propostas em `{cfg.memory_dir}/decisions/`)")

    stale = [
        n
        for n in memory.notes
        if stale_reason(n.review_by, n.rel, changed, today, cfg.stale_after_days)
    ]
    old_entries = [
        e
        for e in memory.entries
        if e.moment is not None and (today - e.moment.date()).days > cfg.journal_after_days
    ]
    if stale or old_entries:
        parts = []
        if stale:
            parts.append(plural(len(stale), "nota vencida", "notas vencidas"))
        if old_entries:
            parts.append(
                plural(len(old_entries), "registro do diário", "registros do diário")
                + " para triagem"
            )
        markers = sum(sum(count_markers(n.body, cfg.markers).values()) for n in stale)
        if markers:
            parts.append(plural(markers, "marcador de provisório", "marcadores de provisório"))
        lines.append(
            f"- Housekeeping pendente: {', '.join(parts)}. No começo da conversa, ofereça uma "
            "vez `/harness-hacka:housekeeping`, sem insistir."
        )
    if commits:
        lines.append(
            f"- {plural(commits, 'commit', 'commits')} desde o último registro do diário. Ao "
            "fechar o trabalho, ofereça `/harness-hacka:journal`."
        )
    if errors:
        lines.append(
            f"- A auditoria acusa {plural(errors, 'erro', 'erros')} na memória. Rode "
            "`harness-hacka check` antes de confiar no índice."
        )
    return lines


def _decisions_block(memory: Memory) -> _Block:
    live = sorted((d for d in memory.decisions if d.is_live), key=lambda d: d.number)
    dead = [d for d in memory.decisions if not d.is_live]
    full, compact = [], []
    for d in live:
        if d.status == "accepted":
            who = f", {d.decided_by}" if d.decided_by else ""
            rule = f" Regra: {d.rule[0]}" if d.rule else ""
            if len(d.rule) > 1:
                rule += f" (+{len(d.rule) - 1})"
            full.append(f"- {d.number:04d} {d.title} (accepted{who}).{rule}")
        else:
            full.append(f"- {d.number:04d} {d.title} (proposed: ainda não vale).")
        compact.append(f"- {d.number:04d} {d.title} ({d.status})")
    if dead:
        note = f"- (+{len(dead)} superseded, deprecated ou rejected: não siga, veja o substituto)"
        full.append(note)
        compact.append(note)
    return _Block("Decisões", full, compact, pointer=f"`{memory.cfg.memory_dir}/decisions/`")


def _last_session(memory: Memory) -> _Block:
    e = memory.last_entry
    if e is None or e.moment is None:
        return _Block("Última sessão")
    head = f"{e.moment:%Y-%m-%d %H:%M}"
    if e.author:
        head += f" · {e.author}"
    if e.status:
        head += f" · {e.status}"
    head += f" · {e.title} (`{e.rel}`)"
    steps = [f"- {s}" for s in e.next_steps]
    full = [head, *(["Next steps:", *steps] if steps else [])]
    compact = [head, *(["Next steps:", *steps[:3]] if steps else [])]
    if len(steps) > 3:
        compact.append(f"- (+{len(steps) - 3} no registro)")
    return _Block("Última sessão", full, compact, pointer=f"`{e.rel}`")


def _lessons(memory: Memory) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    recent = sorted(memory.entries, key=lambda e: e.moment or datetime.min, reverse=True)
    for item in [*(t for e in recent for t in e.dead_ends), *reversed(memory.lessons)]:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            items.append(f"- {key}")
    return items  # do mais novo para o mais velho


# Arquivos de instrução que o agente carrega sozinho no início da sessão.
_INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


def _notes_block(memory: Memory) -> _Block:
    for path in index.index_files(memory):
        if path.name in _INSTRUCTION_FILES and index.has_region(
            path.read_text(encoding="utf-8-sig"), "index"
        ):
            return _Block("Notas")  # o arquivo de instrução já carrega o índice; não repetir
    lines = [f"- `{n.rel}`: ler quando {n.read_when or '(sem read_when)'}" for n in memory.notes]
    return _Block("Notas", lines, None, pointer=f"`{memory.cfg.memory_dir}/`")


def _join(header: list[str], blocks: list[_Block]) -> str:
    lines = list(header)
    for block in blocks:
        body = block.render()
        if body:
            lines += ["", *body]
    return "\n".join(lines).strip() + "\n"


def build(memory: Memory, today: date, subagent: bool = False) -> str:
    cfg = memory.cfg
    limit = min(cfg.max_chars, SUBAGENT_MAX_CHARS) if subagent else cfg.max_chars
    header = [
        "## Memória do projeto (harness-hacka)",
        f"A memória fica em `{cfg.memory_dir}/`. Este resumo aponta; a nota é a fonte. Antes de "
        "agir sobre um assunto, leia a nota dele.",
    ]
    decisions = _decisions_block(memory)
    lesson_items = _lessons(memory)
    lessons = _Block("Não repetir", list(lesson_items), pointer=f"`{cfg.memory_dir}/journal/`")

    if subagent:
        blocks = [decisions, lessons]
        cuts = [
            lambda: _trim_items(lessons, lesson_items, blocks, header, limit),
            lambda: setattr(decisions, "mode", "compact"),
            lambda: setattr(lessons, "mode", "hidden"),
            lambda: setattr(decisions, "mode", "hidden"),
        ]
    else:
        last = memory.last_entry
        commits = git.commits_since(cfg.root, last.moment) if last else []
        changed = git.last_changed(cfg.root, cfg.memory.relative_to(cfg.root))
        errors = sum(1 for f in audit(memory, today, changed) if f.level == "error")
        pending = _Block("Pendências", _pending(memory, today, changed, len(commits), errors))
        last_session = _last_session(memory)
        notes = _notes_block(memory)
        blocks = [pending, decisions, last_session, lessons, notes]
        cuts = [
            lambda: setattr(notes, "mode", "hidden"),
            lambda: _trim_items(lessons, lesson_items, blocks, header, limit),
            lambda: setattr(decisions, "mode", "compact"),
            lambda: setattr(last_session, "mode", "compact"),
            lambda: setattr(lessons, "mode", "hidden"),
            lambda: setattr(decisions, "mode", "hidden"),
        ]

    text = _join(header, blocks)
    for cut in cuts:
        if len(text) <= limit:
            break
        cut()
        text = _join(header, blocks)
    return text


def _trim_items(
    block: _Block, items: list[str], blocks: list[_Block], header: list[str], limit: int
) -> None:
    """Tira as lições mais antigas até caber, e avisa quantas ficaram de fora."""
    if not items:
        return
    keep = len(items)
    while keep > 0:
        keep -= 1
        rest = len(items) - keep
        block.lines = [*items[:keep], f"- (+{rest} mais antigas em {block.pointer})"]
        if len(_join(header, blocks)) <= limit:
            return
    block.mode = "hidden"

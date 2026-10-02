"""O modelo da memória: notas, decisões, registros do diário e o arquivo.

```
memory/
├── *.md         notas: o que vale hoje, cada uma com `read_when` e validade
├── lessons.md   o que não repetir (qualquer nota com `type: lessons`)
├── decisions/   por que é assim: NNNN-titulo.md, proposed -> accepted -> superseded
├── journal/     o que aconteceu: um arquivo por sessão, AAAA-MM-DD-HHMM-titulo.md
└── archive/     o que já não vale. Nada é apagado; sai do caminho, não do histórico
```

Um arquivo por registro de diário, e não um por mês: com quatro pessoas juntando na mesma
branch, dois registros no fim do mesmo arquivo viram conflito de merge a cada sessão.

Os status de decisão seguem o MADR (Markdown Architectural Decision Records).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import frontmatter as fm
from . import markdown as md
from .config import Config

STATUSES = ("proposed", "rejected", "accepted", "deprecated", "superseded")
LIVE = ("proposed", "accepted")
# Vocabulário que as pessoas escrevem de verdade, normalizado para o canônico.
STATUS_ALIASES = {
    "proposta": "proposed",
    "proposto": "proposed",
    "aceita": "accepted",
    "aceito": "accepted",
    "aprovada": "accepted",
    "aprovado": "accepted",
    "implemented": "accepted",
    "implementada": "accepted",
    "rejeitada": "rejected",
    "descartada": "rejected",
    "recusada": "rejected",
    "obsoleta": "deprecated",
    "substituida": "superseded",
    "substituída": "superseded",
    "substituido": "superseded",
    "substituído": "superseded",
}

# Chaves e seções de decisão como o harness-memoria e quem escreve em português as grafam.
# Lidas sem conversão, como os status: trocar o nome da chave ou do título numa decisão
# `accepted` seria reescrever decisão que não se reescreve.
FIELD_ALIASES = {
    "date": ("date", "data"),
    "decided_by": ("decided_by", "decidido_por", "decidido-por"),
    "supersedes": ("supersedes", "substitui"),
    "superseded_by": ("superseded_by", "substituido_por", "substituido-por"),
}
RULE_SECTIONS = ("Rule", "Regra")

ENTRY_STATUSES = ("done", "partial", "blocked")
ENTRY_STATUS_ALIASES = {
    "concluido": "done",
    "concluído": "done",
    "parcial": "partial",
    "bloqueado": "blocked",
}

JOURNAL_SECTIONS = ("Changes", "Dead ends", "Verification", "Next steps")
DEAD_ENDS = "Dead ends"
NEXT_STEPS = "Next steps"
_NOTHING = re.compile(r"^(none|nenhuma|nenhum|nada|n/a|-)\.?$", re.IGNORECASE)
# Trecho dos modelos que ninguém preencheu: `{mudança concreta e verificável}`.
PLACEHOLDER = re.compile(r"\{[^{}\n\"':]{6,}\}")

_DECISION_NAME = re.compile(r"^(\d{4})-[\w-]+\.md$")
_ENTRY_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:-(\d{2})(\d{2}))?(?:-[\w-]+)?\.md$")
_DECISION_TITLE_PREFIX = re.compile(r"^(?:ADR[- ]?)?\d{1,4}\s*[—–:.-]\s*", re.IGNORECASE)


def is_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER.search(text))


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def count_markers(text: str, markers: tuple[str, ...]) -> dict[str, int]:
    """Quantas vezes cada marcador de provisório aparece no texto.

    Diferencia maiúsculas de propósito: sem isso, o marcador `TODO` casa com a palavra
    "todo" de qualquer frase em português.
    """
    counts = {m: text.count(m) for m in markers}
    return {m: n for m, n in counts.items() if n}


def normalize_status(value: str) -> str:
    raw = value.strip().casefold()
    return STATUS_ALIASES.get(raw, raw)


def normalize_entry_status(value: str) -> str:
    raw = value.strip().casefold()
    return ENTRY_STATUS_ALIASES.get(raw, raw)


def field_key(fields: dict[str, object], name: str) -> str:
    """A grafia da chave `name` que este frontmatter usa; a canônica se nenhuma aparece."""
    for key in FIELD_ALIASES.get(name, (name,)):
        if key in fields:
            return key
    return name


def rule_lines(body: str) -> list[str] | None:
    for name in RULE_SECTIONS:
        lines = md.section(body, name)
        if lines is not None:
            return lines
    return None


def parse_numbers(values: list[str]) -> list[int]:
    """`["ADR-0003", "0004", "5"]` -> `[3, 4, 5]`."""
    result = []
    for value in values:
        match = re.search(r"(\d{1,4})", value)
        if match:
            result.append(int(match.group(1)))
    return result


@dataclass
class Document:
    path: Path  # relativo à raiz do projeto
    fields: dict[str, object]
    body: str
    title: str
    # linhas que o frontmatter ocupa: somadas à linha do corpo, dão a linha do arquivo
    offset: int = 0

    @property
    def rel(self) -> str:
        return self.path.as_posix()


@dataclass
class Note(Document):
    read_when: str = ""
    summary: str = ""
    review_by: date | None = None
    kind: str = ""


@dataclass
class Decision(Document):
    number: int = 0
    status: str = ""
    raw_status: str = ""
    decision_date: date | None = None  # a chave `date` do frontmatter
    decided_by: str = ""
    supersedes: list[int] = field(default_factory=list)
    superseded_by: list[int] = field(default_factory=list)
    rule: list[str] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.status in LIVE


@dataclass
class Entry(Document):
    moment: datetime | None = None
    author: str = ""
    status: str = ""
    raw_status: str = ""

    def _items(self, name: str) -> list[str]:
        lines = md.section(self.body, name)
        return [
            i
            for i in md.list_items(lines)
            if not _NOTHING.match(i.strip()) and not is_placeholder(i)
        ]

    @property
    def dead_ends(self) -> list[str]:
        return self._items(DEAD_ENDS)

    @property
    def next_steps(self) -> list[str]:
        return self._items(NEXT_STEPS)


@dataclass
class Memory:
    cfg: Config
    notes: list[Note] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    housekeeping_runs: list[Path] = field(default_factory=list)
    archived: list[Path] = field(default_factory=list)
    problems: list[tuple[str, str]] = field(default_factory=list)

    def decision(self, number: int) -> Decision | None:
        for d in self.decisions:
            if d.number == number:
                return d
        return None

    @property
    def last_entry(self) -> Entry | None:
        dated = [e for e in self.entries if e.moment is not None]
        return max(dated, key=lambda e: e.moment) if dated else None  # type: ignore[arg-type, return-value]

    @property
    def lessons(self) -> list[str]:
        """Itens das notas `type: lessons`, o destino durável dos dead ends."""
        items: list[str] = []
        for note in self.notes:
            if note.kind == "lessons":
                items.extend(md.list_items(note.body.splitlines()))
        return items


def _read(root: Path, path: Path, memory: Memory) -> tuple[dict[str, object], str, int] | None:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        memory.problems.append((rel, f"não consegui ler: {error}"))
        return None
    try:
        fields, body = fm.split(text)
    except fm.InvalidFrontmatter as error:
        memory.problems.append((rel, str(error)))
        return None
    return fields, body, text.count("\n") - body.count("\n")


def _is_special(path: Path) -> bool:
    return path.name.casefold() == "readme.md" or path.name.startswith("_")


def load(cfg: Config) -> Memory:
    root = cfg.root
    memory = Memory(cfg=cfg)
    if not cfg.memory.is_dir():
        return memory

    special = {cfg.decisions, cfg.journal, cfg.archive}
    for path in sorted(cfg.memory.rglob("*.md")):
        if _is_special(path) or any(p in special for p in path.parents):
            continue
        read = _read(root, path, memory)
        if read is None:
            continue
        fields, body, offset = read
        memory.notes.append(
            Note(
                path=path.relative_to(root),
                fields=fields,
                body=body,
                offset=offset,
                title=md.title(body) or path.stem,
                read_when=fm.text(fields, "read_when"),
                summary=fm.text(fields, "summary"),
                review_by=fm.parse_date(fields.get("review_by")),
                kind=fm.text(fields, "type").casefold(),
            )
        )

    if cfg.decisions.is_dir():
        for path in sorted(cfg.decisions.glob("*.md")):
            if _is_special(path):
                continue
            read = _read(root, path, memory)
            if read is None:
                continue
            fields, body, offset = read
            match = _DECISION_NAME.match(path.name)
            raw = fm.text(fields, "status")
            memory.decisions.append(
                Decision(
                    path=path.relative_to(root),
                    fields=fields,
                    body=body,
                    offset=offset,
                    title=_DECISION_TITLE_PREFIX.sub("", md.title(body)).strip() or path.stem,
                    number=int(match.group(1)) if match else 0,
                    status=normalize_status(raw),
                    raw_status=raw,
                    decision_date=fm.parse_date(fields.get(field_key(fields, "date"))),
                    decided_by=fm.text(fields, field_key(fields, "decided_by")),
                    supersedes=parse_numbers(fm.as_list(fields, field_key(fields, "supersedes"))),
                    superseded_by=parse_numbers(
                        fm.as_list(fields, field_key(fields, "superseded_by"))
                    ),
                    rule=[i for i in md.list_items(rule_lines(body)) if not is_placeholder(i)],
                )
            )

    if cfg.journal.is_dir():
        for path in sorted(cfg.journal.glob("*.md")):
            if _is_special(path):
                continue
            read = _read(root, path, memory)
            if read is None:
                continue
            fields, body, offset = read
            raw = fm.text(fields, "status")
            memory.entries.append(
                Entry(
                    path=path.relative_to(root),
                    fields=fields,
                    body=body,
                    offset=offset,
                    title=md.title(body) or path.stem,
                    moment=_moment(path.name),
                    author=fm.text(fields, "author"),
                    status=normalize_entry_status(raw),
                    raw_status=raw,
                )
            )

    if cfg.archive.is_dir():
        for path in sorted(cfg.archive.rglob("*.md")):
            if _is_special(path):
                continue
            rel = path.relative_to(root)
            if path.parent == cfg.archive / "housekeeping":
                memory.housekeeping_runs.append(rel)
            else:
                memory.archived.append(rel)
    return memory


def _moment(name: str) -> datetime | None:
    match = _ENTRY_NAME.match(name)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    try:
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))
    except ValueError:
        return None


def date_from_name(path: Path) -> date | None:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", path.name)
    if not match:
        return None
    try:
        return date(*(int(g) for g in match.groups()))
    except ValueError:
        return None

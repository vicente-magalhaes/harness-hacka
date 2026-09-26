"""A auditoria da memória. Determinística, sem LLM: é o que roda no CI e alimenta o inspector.

Metade dos cheques não procura o que falta, procura o que mente: link para arquivo que
sumiu, índice defasado, citação de decisão substituída. Documentação ausente quase não
atrapalha um agente; documentação errada atrapalha, porque ele age em cima dela.

`error` reprova. `warning` não reprova: vira candidato do housekeeping.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from . import index, sensitive
from . import markdown as md
from .memory import (
    ENTRY_STATUSES,
    JOURNAL_SECTIONS,
    PLACEHOLDER,
    STATUSES,
    Decision,
    Document,
    Memory,
)

_CITATION = re.compile(r"\b(?:ADR|decis[aã]o|decision)[\s-]?(\d{4})\b", re.IGNORECASE)
_DECISION_LINK = re.compile(r"decisions/(\d{4})-[\w-]+\.md")
# Linha que já avisa que a decisão morreu não é ponteiro velho.
_CAVEAT = re.compile(r"supersed|deprecat|reject|substitu|descart|hist[oó]ri", re.IGNORECASE)
_DECISION_FILENAME = re.compile(r"^\d{4}-[a-z0-9][a-z0-9-]*\.md$")
_ENTRY_FILENAME = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9][a-z0-9-]*\.md$")
_DEAD = ("superseded", "deprecated", "rejected")


@dataclass(frozen=True)
class Finding:
    level: str  # "error" ou "warning"
    code: str
    file: str
    message: str
    line: int | None = None

    def format(self) -> str:
        mark = "x" if self.level == "error" else "!"
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"{mark} {where}  {self.message}  [{self.code}]"

    def as_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "code": self.code,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }


def note_age(rel: str, changed: dict[str, date], today: date) -> int:
    when = changed.get(rel)
    return (today - when).days if when else 0


def stale_reason(
    review_by: date | None, rel: str, changed: dict[str, date], today: date, max_days: int
) -> str:
    if review_by is not None:
        # No dia marcado a nota já entra no housekeeping: `review_by` é "revisar neste dia".
        if review_by == today:
            return "revisão marcada para hoje (`review_by`)"
        return f"venceu em {review_by.isoformat()} (`review_by`)" if review_by < today else ""
    age = note_age(rel, changed, today)
    if max_days and age > max_days:
        return f"sem alteração há {age} dias (limite de {max_days})"
    return ""


def audit(memory: Memory, today: date, changed: dict[str, date]) -> list[Finding]:
    findings: list[Finding] = []
    for rel, problem in memory.problems:
        findings.append(Finding("error", "frontmatter", rel, problem))
    findings += _check_notes(memory, today, changed)
    findings += _check_decisions(memory, today)
    findings += _check_entries(memory, today)
    findings += _check_links(memory)
    findings += _check_dead_references(memory)
    findings += _check_indexes(memory)
    findings += _check_sensitive(memory)
    findings += _check_placeholders(memory)
    return findings


def _check_notes(memory: Memory, today: date, changed: dict[str, date]) -> list[Finding]:
    cfg = memory.cfg
    findings = []
    for note in memory.notes:
        if not note.read_when:
            findings.append(
                Finding(
                    "error",
                    "missing-read-when",
                    note.rel,
                    "nota sem `read_when` no frontmatter: o índice não diz quando ler",
                )
            )
        raw = note.fields.get("review_by")
        if raw and note.review_by is None:
            findings.append(
                Finding("error", "invalid-date", note.rel, f"`review_by: {raw}` não é data")
            )
        reason = stale_reason(note.review_by, note.rel, changed, today, cfg.stale_after_days)
        if reason:
            findings.append(Finding("warning", "stale", note.rel, reason))
    return findings


def _check_decisions(memory: Memory, today: date) -> list[Finding]:
    cfg = memory.cfg
    findings = []
    repeated = [n for n, q in Counter(d.number for d in memory.decisions).items() if q > 1]
    for number in repeated:
        names = ", ".join(d.path.name for d in memory.decisions if d.number == number)
        findings.append(
            Finding(
                "error",
                "decision-duplicate",
                cfg.decisions.relative_to(cfg.root).as_posix(),
                f"número {number:04d} usado mais de uma vez ({names}). Renumere a mais nova",
            )
        )
    for d in memory.decisions:
        if not _DECISION_FILENAME.match(d.path.name):
            findings.append(
                Finding(
                    "error",
                    "decision-filename",
                    d.rel,
                    "nome fora do formato NNNN-titulo-com-hifens.md",
                )
            )
        if d.status not in STATUSES:
            value = d.raw_status or "(vazio)"
            findings.append(
                Finding(
                    "error",
                    "decision-status",
                    d.rel,
                    f"status '{value}' inválido. Use: {', '.join(STATUSES)}",
                )
            )
        if d.decision_date is None:
            findings.append(
                Finding("error", "decision-date", d.rel, "sem `date:` válida (AAAA-MM-DD)")
            )
        if d.status == "accepted" and not d.decided_by:
            findings.append(
                Finding(
                    "error",
                    "decision-owner",
                    d.rel,
                    "accepted sem `decided_by`. Aceitar é ato de uma pessoa: diga qual",
                )
            )
        if d.status == "accepted" and not d.rule:
            findings.append(
                Finding(
                    "warning",
                    "decision-rule",
                    d.rel,
                    "accepted sem `## Rule`: o briefing não tem o que dizer sobre ela",
                )
            )
        if (
            d.status == "proposed"
            and d.decision_date is not None
            and (today - d.decision_date).days > cfg.proposal_after_days
        ):
            findings.append(
                Finding(
                    "warning",
                    "proposal-waiting",
                    d.rel,
                    f"proposed há {(today - d.decision_date).days} dias esperando uma pessoa",
                )
            )
        findings += _check_supersession(memory, d)
    return findings


def _check_supersession(memory: Memory, d: Decision) -> list[Finding]:
    findings = []
    if d.status == "accepted":
        for n in d.supersedes:
            old = memory.decision(n)
            if old is None:
                findings.append(
                    Finding("error", "supersession", d.rel, f"supersedes {n:04d}, que não existe")
                )
            elif old.status != "superseded" or d.number not in old.superseded_by:
                findings.append(
                    Finding(
                        "error",
                        "supersession",
                        old.rel,
                        f"{d.number:04d} foi aceita e substitui esta. Marque "
                        f"`status: superseded` e `superseded_by: [{d.number:04d}]`",
                    )
                )
    if d.status == "superseded":
        if not d.superseded_by:
            findings.append(
                Finding(
                    "error",
                    "supersession",
                    d.rel,
                    "superseded sem `superseded_by`. Se nada a substitui, o status é deprecated",
                )
            )
        for n in d.superseded_by:
            new = memory.decision(n)
            if new is None:
                findings.append(
                    Finding(
                        "error", "supersession", d.rel, f"superseded_by {n:04d}, que não existe"
                    )
                )
            elif new.status != "accepted" or d.number not in new.supersedes:
                findings.append(
                    Finding(
                        "error",
                        "supersession",
                        new.rel,
                        f"precisa estar accepted e declarar `supersedes: [{d.number:04d}]` "
                        f"para {d.number:04d} valer como superseded",
                    )
                )
    return findings


def _check_entries(memory: Memory, today: date) -> list[Finding]:
    cfg = memory.cfg
    findings = []
    limit = today - timedelta(days=cfg.journal_after_days)
    for e in memory.entries:
        if not _ENTRY_FILENAME.match(e.path.name) or e.moment is None:
            findings.append(
                Finding(
                    "error",
                    "entry-filename",
                    e.rel,
                    "nome fora do formato AAAA-MM-DD-HHMM-titulo.md",
                )
            )
        missing = [s for s in JOURNAL_SECTIONS if md.section(e.body, s) is None]
        if missing:
            findings.append(
                Finding(
                    "error",
                    "entry-sections",
                    e.rel,
                    "faltam as seções: " + ", ".join(f"## {s}" for s in missing),
                )
            )
        if e.status not in ENTRY_STATUSES:
            findings.append(
                Finding(
                    "error",
                    "entry-status",
                    e.rel,
                    f"`status: {e.raw_status or '(vazio)'}` inválido. "
                    f"Use: {', '.join(ENTRY_STATUSES)}",
                )
            )
        if e.moment is not None and e.moment.date() < limit:
            days = (today - e.moment.date()).days
            findings.append(
                Finding(
                    "warning",
                    "journal-triage",
                    e.rel,
                    f"registro de {days} dias: promova o que vale e arquive o resto",
                )
            )
    return findings


def _active_documents(memory: Memory) -> list[Path]:
    cfg = memory.cfg
    paths = [cfg.root / d.path for d in (*memory.notes, *memory.decisions, *memory.entries)]
    for readme in (
        cfg.memory / "README.md",
        cfg.decisions / "README.md",
        cfg.journal / "README.md",
    ):
        if readme.is_file():
            paths.append(readme)
    for extra in cfg.index_files:
        target = cfg.root / extra
        if target.is_file() and target not in paths:
            paths.append(target)
    return paths


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _check_links(memory: Memory) -> list[Finding]:
    root = memory.cfg.root
    findings = []
    for path in _active_documents(memory):
        for line, target in md.relative_links(_read_text(path)):
            resolved = (
                (root / target.lstrip("/")) if target.startswith("/") else path.parent / target
            )
            if not resolved.exists():
                findings.append(
                    Finding(
                        "error",
                        "broken-link",
                        path.relative_to(root).as_posix(),
                        f"link para `{target}`, que não existe",
                        line,
                    )
                )
    return findings


def _check_dead_references(memory: Memory) -> list[Finding]:
    root = memory.cfg.root
    dead = {d.number: d for d in memory.decisions if d.status in _DEAD}
    if not dead:
        return []
    findings = []
    targets = [root / n.path for n in memory.notes]
    targets += [root / f for f in memory.cfg.index_files if (root / f).is_file()]
    for path in targets:
        for line_no, line in md.lines_outside_code(_read_text(path)):
            cited = {int(n) for n in _CITATION.findall(line)}
            cited |= {int(n) for n in _DECISION_LINK.findall(line)}
            for n in sorted(cited & set(dead)):
                gone = dead[n]
                successors = {f"{s:04d}" for s in gone.superseded_by}
                if _CAVEAT.search(line) or any(s in line for s in successors):
                    continue
                hint = (
                    f"foi substituída por {', '.join(sorted(successors))}"
                    if successors
                    else f"está {gone.status}"
                )
                findings.append(
                    Finding(
                        "error",
                        "dead-reference",
                        path.relative_to(root).as_posix(),
                        f"cita a decisão {n:04d}, que {hint}. Aponte para a que vale",
                        line_no,
                    )
                )
    return findings


def _check_indexes(memory: Memory) -> list[Finding]:
    root = memory.cfg.root
    return [
        Finding(
            "error",
            "outdated-index",
            path.relative_to(root).as_posix(),
            "índice defasado em relação aos arquivos. Rode `harness-hacka index --update`",
        )
        for path in index.outdated(memory)
    ]


def _check_sensitive(memory: Memory) -> list[Finding]:
    cfg = memory.cfg
    paths = sorted(cfg.memory.rglob("*.md")) if cfg.memory.is_dir() else []
    paths += [cfg.root / f for f in cfg.index_files if (cfg.root / f).is_file()]
    findings = []
    for path in paths:
        text = _read_text(path)
        rel = path.relative_to(cfg.root).as_posix()
        for kind in sensitive.find_secrets(text):
            findings.append(
                Finding(
                    "error",
                    "secret",
                    rel,
                    f"parece conter {kind}. Tire daqui e troque a chave: o git guarda o histórico",
                )
            )
        for kind in sensitive.find_personal_data(text):
            findings.append(
                Finding(
                    "warning", "personal-data", rel, f"parece conter {kind}. Memória não guarda"
                )
            )
    return findings


def _first_placeholder_line(doc: Document) -> int | None:
    """Linha (no arquivo) do primeiro trecho de modelo não preenchido, fora de código."""
    for number, line in md.lines_outside_code(doc.body):
        if PLACEHOLDER.search(line):
            return number + doc.offset
    return None


def _check_placeholders(memory: Memory) -> list[Finding]:
    findings = []
    for e in memory.entries:
        line = _first_placeholder_line(e)
        if line:
            findings.append(
                Finding(
                    "error",
                    "unfilled-template",
                    e.rel,
                    "registro com trecho do modelo sem preencher, como `{...}`",
                    line,
                )
            )
    for d in memory.decisions:
        line = _first_placeholder_line(d)
        if line and d.status in ("proposed", "accepted"):
            findings.append(
                Finding(
                    "error" if d.status == "accepted" else "warning",
                    "unfilled-template",
                    d.rel,
                    "decisão com trecho do modelo sem preencher, como `{...}`",
                    line,
                )
            )
    return findings

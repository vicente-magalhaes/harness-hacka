"""Índices gerados a partir dos arquivos, nunca escritos à mão.

Um índice mantido à mão apodrece em silêncio, e ponteiro velho engana mais que ponteiro
nenhum. Aqui a fonte da verdade é o frontmatter de cada nota e de cada decisão. O índice
vive entre marcadores num arquivo qualquer (CLAUDE.md, memory/README.md):

    <!-- harness-hacka:index -->       tabela de notas: arquivo, conteúdo, ler quando
    <!-- /harness-hacka:index -->

    <!-- harness-hacka:decisions -->   tabela de decisões: número, título, status
    <!-- /harness-hacka:decisions -->

`harness-hacka index --update` reescreve o miolo. O `check` reprova quando ele está defasado.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .memory import Memory

_REGION = re.compile(
    r"(<!--\s*harness-hacka:(?P<name>index|decisions)\s*-->)(?P<inner>.*?)"
    r"(<!--\s*/harness-hacka:(?P=name)\s*-->)",
    re.DOTALL,
)


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "\\|").split())


def _link(target: Path, base: Path) -> str:
    return Path(os.path.relpath(target, base)).as_posix()


def notes_table(memory: Memory, base: Path) -> str:
    root = memory.cfg.root
    lines = ["| Arquivo | Conteúdo | Ler quando |", "|---|---|---|"]
    for note in memory.notes:
        target = _link(root / note.path, base)
        contents = _cell(note.summary or note.title)
        when = _cell(note.read_when) or "(sem `read_when`)"
        lines.append(f"| [{target}]({target}) | {contents} | {when} |")
    return "\n".join(lines)


def decisions_table(memory: Memory, base: Path) -> str:
    root = memory.cfg.root
    lines = ["| Decisão | Título | Status |", "|---|---|---|"]
    for d in sorted(memory.decisions, key=lambda d: d.number):
        target = _link(root / d.path, base)
        status = d.status or "(sem status)"
        if d.status == "superseded" and d.superseded_by:
            status += " by " + ", ".join(f"{n:04d}" for n in d.superseded_by)
        lines.append(f"| [{d.number:04d}]({target}) | {_cell(d.title)} | {status} |")
    return "\n".join(lines)


def index_files(memory: Memory) -> list[Path]:
    cfg = memory.cfg
    candidates = [cfg.root / f for f in cfg.index_files]
    candidates += [cfg.memory / "README.md", cfg.decisions / "README.md"]
    seen: list[Path] = []
    for c in candidates:
        if c.is_file() and c not in seen:
            seen.append(c)
    return seen


def render(text: str, memory: Memory, base: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        table = notes_table(memory, base) if name == "index" else decisions_table(memory, base)
        return f"{match.group(1)}\n{table}\n{match.group(4)}"

    return _REGION.sub(replace, text)


def has_region(text: str, name: str | None = None) -> bool:
    return any(name in (None, m.group("name")) for m in _REGION.finditer(text))


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def outdated(memory: Memory) -> list[Path]:
    """Arquivos cujo índice não bate com o que os arquivos da memória dizem hoje."""
    result = []
    for path in index_files(memory):
        text = path.read_text(encoding="utf-8-sig")
        if has_region(text) and _normalize(render(text, memory, path.parent)) != _normalize(text):
            result.append(path)
    return result


def update(memory: Memory) -> list[Path]:
    written = []
    for path in outdated(memory):
        # Lê em bytes: read_text converte CRLF sozinho e esconderia o fim de linha original.
        text = path.read_bytes().decode("utf-8-sig")
        # Mantém o fim de linha do arquivo: trocar CRLF por LF viraria um diff de tudo.
        newline = "\r\n" if "\r\n" in text else "\n"
        path.write_text(
            render(_normalize(text), memory, path.parent), encoding="utf-8", newline=newline
        )
        written.append(path)
    return written

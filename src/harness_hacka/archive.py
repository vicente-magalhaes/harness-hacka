"""Arquivar: tirar da memória ativa sem apagar.

O arquivo vai para `memory/archive/` mantendo o caminho relativo, com `archived_at` e `reason`
no frontmatter. Com `git mv`, o histórico acompanha. Decisão não se arquiva: muda de status
(superseded, deprecated, rejected) e continua em `decisions/`, porque é a trilha do porquê.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import frontmatter as fm
from . import git
from .memory import Memory


class NotArchivable(ValueError):
    pass


def archive(memory: Memory, rel_path: str, reason: str, today: date) -> Path:
    cfg = memory.cfg
    root = cfg.root.resolve()
    source = (root / rel_path).resolve()
    if not source.is_file():
        raise NotArchivable(f"{rel_path} não existe")
    if not reason.strip():
        raise NotArchivable("diga o motivo: é o que explica, depois, por que saiu")
    try:
        relative = source.relative_to(cfg.memory.resolve())
    except ValueError:
        raise NotArchivable(f"{rel_path} está fora de {cfg.memory_dir}/") from None
    if relative.parts[0] == "archive":
        raise NotArchivable(f"{rel_path} já está arquivado")
    if relative.parts[0] == "decisions":
        raise NotArchivable(
            "decisão não se arquiva: marque superseded, deprecated ou rejected e deixe onde está"
        )
    if source.name.casefold() == "readme.md":
        raise NotArchivable("README da memória não se arquiva")

    target = cfg.archive.resolve() / relative
    if target.exists():
        n = 2
        while target.with_name(f"{target.stem}-{n}{target.suffix}").exists():
            n += 1
        target = target.with_name(f"{target.stem}-{n}{target.suffix}")

    git.move(root, source, target)
    text = target.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n")
    clean_reason = " ".join(reason.split()).replace('"', "'")
    text = fm.set_field(text, "archived_at", today.isoformat())
    text = fm.set_field(text, "reason", f'"{clean_reason}"')
    target.write_text(text, encoding="utf-8", newline=newline)
    # Se o git moveu, o motivo entra no mesmo passo: arquivar é uma operação só no index.
    if git.is_tracked(root, target.relative_to(root)):
        git.add(root, target.relative_to(root))
    return target

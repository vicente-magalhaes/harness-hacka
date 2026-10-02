"""Criação de arquivos a partir dos modelos: decisão, registro do diário, housekeeping e esqueleto.

Numeração e nome de arquivo ficam aqui, e não na mão do agente: dois registros com o mesmo
nome ou duas decisões 0004 são o tipo de erro que só aparece no merge.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from .config import CONFIG_FILE
from .memory import Memory

TEMPLATES = Path(__file__).parent / "templates"


def slugify(title: str, limit: int = 48) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", plain.casefold()).strip("-")
    if len(base) > limit:
        base = base[:limit].rsplit("-", 1)[0] or base[:limit]
    return base or "sem-titulo"


def render_template(name: str, **values: str) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _free_path(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 100):
        other = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not other.exists():
            return other
    raise FileExistsError(f"não achei nome livre para {path.name}")


def next_number(memory: Memory) -> int:
    return max((d.number for d in memory.decisions), default=0) + 1


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def new_decision(memory: Memory, title: str, today: date) -> Path:
    number = next_number(memory)
    path = _free_path(memory.cfg.decisions / f"{number:04d}-{slugify(title)}.md")
    text = render_template(
        "decision.md", number=f"{number:04d}", title=title, date=today.isoformat()
    )
    return _write(path, text)


def new_entry(memory: Memory, title: str, author: str, now: datetime) -> Path:
    path = _free_path(memory.cfg.journal / f"{now:%Y-%m-%d-%H%M}-{slugify(title)}.md")
    text = render_template("journal.md", title=title, author=author or "(preencha)")
    return _write(path, text)


def new_housekeeping(memory: Memory, author: str, now: datetime) -> Path:
    path = _free_path(memory.cfg.archive / "housekeeping" / f"{now:%Y-%m-%d-%H%M}.md")
    text = render_template(
        "housekeeping.md", date=now.date().isoformat(), author=author or "(preencha)"
    )
    return _write(path, text)


# De onde os agentes instalam o harness. É o endereço do próprio harness, não política de projeto.
PLUGIN_SOURCE = "vicente-magalhaes/harness-hacka"
PLUGIN_GIT = f"git+https://github.com/{PLUGIN_SOURCE}"

DEVIN_NEXT_STEPS = f"""
Devin: o que estes arquivos fazem e o que falta.
- .devin/config.json pede o plugin ao Devin: skills /harness-hacka:* na nuvem, no CLI e no
  Desktop. Hooks de plugin, o Devin só roda no CLI e no Desktop.
- .devin/hooks.v1.json registra os hooks pelo repositório e chama `harness-hacka` do PATH.
  Na nuvem, instale o CLI no blueprint do repositório:
      initialize: |
        pip install uv
        uv tool install {PLUGIN_GIT}
  A documentação do Devin não diz se a nuvem roda hooks de repositório. Para conferir,
  peça numa sessão: rode `harness-hacka events`.
"""


def _hook_command(name: str) -> str:
    # POSIX: a nuvem do Devin é Linux. Sem o CLI no PATH, avisa e libera em vez de falhar.
    return (
        f"if command -v harness-hacka >/dev/null 2>&1; then exec harness-hacka hook {name} "
        f"--agent devin; fi; echo '[harness-hacka] harness-hacka fora do PATH, hook {name} "
        f"desligado. Instale com: uv tool install {PLUGIN_GIT}' >&2"
    )


def devin_hooks() -> dict[str, object]:
    def entry(name: str, timeout: int, matcher: str | None = None) -> dict[str, object]:
        hook = {"type": "command", "command": _hook_command(name), "timeout": timeout}
        return {**({"matcher": matcher} if matcher else {}), "hooks": [hook]}

    return {
        "SessionStart": [entry("session-start", 20)],
        "UserPromptSubmit": [entry("approval", 10)],
        "PreToolUse": [entry("guard", 10, "^(read|write|edit|apply_patch|notebook_edit|exec)$")],
        "PostToolUse": [entry("triggers", 10, "^(write|edit|apply_patch|notebook_edit)$")],
    }


def devin(root: Path) -> tuple[list[Path], list[Path]]:
    """Os arquivos que o Devin lê no projeto. Devolve (criados, já existiam)."""
    import json

    targets = {
        root / ".devin" / "config.json": {"requiredPlugins": [PLUGIN_SOURCE]},
        root / ".devin" / "hooks.v1.json": devin_hooks(),
    }
    created, skipped = [], []
    for path, data in targets.items():
        if path.exists():
            skipped.append(path)
        else:
            created.append(_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n"))
    return created, skipped


def skeleton(root: Path, memory_dir: str, project: str, profile: str) -> list[Path]:
    """Cria o que faltar. Nunca sobrescreve: o histórico do projeto vale mais que o modelo."""
    config_text = render_template("config.json", project=project, profile=profile)
    if memory_dir != "memory":
        # Só escreve `memory_dir` quando difere do padrão.
        config_text = config_text.replace(
            f'"profile": "{profile}"', f'"profile": "{profile}",\n  "memory_dir": "{memory_dir}"'
        )
    targets = {
        root / CONFIG_FILE: config_text,
        root / memory_dir / "README.md": render_template("memory-README.md"),
        root / memory_dir / "decisions" / "README.md": render_template("decisions-README.md"),
        root / memory_dir / "journal" / "README.md": render_template("journal-README.md"),
        root / memory_dir / "archive" / "README.md": render_template("archive-README.md"),
    }
    created = []
    for path, text in targets.items():
        if not path.exists():
            created.append(_write(path, text))
    return created

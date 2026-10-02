"""Configuração: o gate, os defaults, os perfis de stack e a validação.

`.claude/harness-hacka.json` na raiz do projeto é o gate. Sem ele, todo hook sai calado: dá
para deixar o plugin habilitado no nível do usuário sem que ele aja em projeto que não pediu.

Config presente e inválida levanta `InvalidConfig`. O hook mostra o erro e não age; o
`check` reprova. Ausente é silêncio, inválida é barulho: quem criou o arquivo quis ligar o
harness e merece saber por que não ligou.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILE = Path(".claude") / "harness-hacka.json"
PROFILES_DIR = Path(__file__).parent / "profiles"

# Todo campo tem default. O projeto escreve só o que difere, e config que repete o default
# mente sobre ter sido pensada.
DEFAULTS: dict[str, Any] = {
    "project": "",
    "profile": "",
    "memory_dir": "memory",
    # Os arquivos de instrução que o agente lê sozinho: AGENTS.md (Devin, Codex, Cursor e o
    # Claude Code sem CLAUDE.md) e CLAUDE.md. Arquivo que não existe é ignorado.
    "index": {"files": ["AGENTS.md", "CLAUDE.md"]},
    "housekeeping": {
        # Nota sem `review_by` vence N dias depois da última alteração no git.
        "stale_after_days": 30,
        # Registro do diário com mais de N dias entra na triagem: promover ou arquivar.
        "journal_after_days": 7,
        # Decisão `proposed` parada há mais de N dias vira lembrete para a pessoa decidir.
        "proposal_after_days": 3,
        # Textos que marcam conteúdo provisório. O inspector confere se ainda valem.
        "markers": [],
    },
    "briefing": {"max_chars": 6000},
    "guard": {
        "secrets": True,
        "memory_secrets": True,
        "human_decisions": True,
        # Nega pular os hooks do git: `--no-verify`, `commit -n`, `HUSKY=0`, `core.hooksPath`.
        "git_hooks": True,
    },
    # glob do caminho -> por que esse arquivo costuma carregar decisão.
    "triggers": {},
    # comandos que servem de evidência no registro da sessão.
    "verify": [],
}

PROFILE_KEYS = {"name", "description", "triggers", "verify", "markers"}


class InvalidConfig(Exception):
    """A config existe, mas não dá para confiar nela."""


@dataclass(frozen=True)
class Config:
    root: Path
    project: str
    profile: str
    memory_dir: str
    index_files: tuple[str, ...]
    stale_after_days: int
    journal_after_days: int
    proposal_after_days: int
    markers: tuple[str, ...]
    max_chars: int
    guard_secrets: bool
    guard_memory_secrets: bool
    human_decisions: bool
    guard_git_hooks: bool
    triggers: dict[str, str]
    verify: tuple[str, ...]

    @property
    def memory(self) -> Path:
        return self.root / self.memory_dir

    @property
    def decisions(self) -> Path:
        return self.memory / "decisions"

    @property
    def journal(self) -> Path:
        return self.memory / "journal"

    @property
    def archive(self) -> Path:
        return self.memory / "archive"


def find_root(start: Path) -> Path | None:
    """Sobe a árvore a partir de `start` até achar `.claude/harness-hacka.json`."""
    current = start.resolve()
    for folder in (current, *current.parents):
        if (folder / CONFIG_FILE).is_file():
            return folder
    return None


def load(root: Path) -> Config | None:
    """Lê a config do projeto. `None` quando o projeto não adotou o harness."""
    path = root / CONFIG_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise InvalidConfig(f"{CONFIG_FILE.as_posix()} não é JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise InvalidConfig(f"{CONFIG_FILE.as_posix()} precisa ser um objeto JSON.")

    _validate(data, DEFAULTS, "")
    final = copy.deepcopy(DEFAULTS)
    profile = data.get("profile") or ""
    if profile:
        _merge(final, _read_profile(profile))
    _merge(final, _strip_annotations(data))
    return _build(root, final)


def available_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def _read_profile(name: str) -> dict[str, Any]:
    path = PROFILES_DIR / f"{name}.json"
    if not path.is_file():
        options = ", ".join(available_profiles()) or "nenhum"
        raise InvalidConfig(f"perfil '{name}' não existe. Disponíveis: {options}.")
    data = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(data) - PROFILE_KEYS
    if unknown:
        raise InvalidConfig(f"perfil '{name}' tem chave desconhecida: {sorted(unknown)}")
    extra: dict[str, Any] = {}
    if "triggers" in data:
        extra["triggers"] = data["triggers"]
    if "verify" in data:
        extra["verify"] = data["verify"]
    if "markers" in data:
        extra["housekeeping"] = {"markers": data["markers"]}
    return extra


def _is_annotation(key: str) -> bool:
    # JSON não tem comentário. Chave que começa com `$` é anotação e nunca é lida.
    return key.startswith("$")


def _strip_annotations(data: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in data.items():
        if _is_annotation(key):
            continue
        clean[key] = _strip_annotations(value) if isinstance(value, dict) else value
    return clean


def _validate(data: dict[str, Any], model: dict[str, Any], prefix: str) -> None:
    for key, value in data.items():
        if _is_annotation(key):
            continue
        name = f"{prefix}{key}"
        if key not in model:
            valid = ", ".join(sorted(model))
            raise InvalidConfig(f"chave desconhecida '{name}'. Válidas aqui: {valid}.")
        expected = model[key]
        if key == "triggers":
            _validate_triggers(value, name)
        elif isinstance(expected, dict):
            if not isinstance(value, dict):
                raise InvalidConfig(f"'{name}' precisa ser um objeto.")
            _validate(value, expected, f"{name}.")
        elif isinstance(expected, bool):
            if not isinstance(value, bool):
                raise InvalidConfig(f"'{name}' precisa ser true ou false.")
        elif isinstance(expected, int):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise InvalidConfig(f"'{name}' precisa ser um inteiro não negativo.")
        elif isinstance(expected, str):
            if not isinstance(value, str):
                raise InvalidConfig(f"'{name}' precisa ser texto.")
        elif isinstance(expected, list) and (
            not isinstance(value, list) or not all(isinstance(v, str) for v in value)
        ):
            raise InvalidConfig(f"'{name}' precisa ser uma lista de textos.")


def _validate_triggers(value: Any, name: str) -> None:
    if not isinstance(value, dict):
        raise InvalidConfig(f"'{name}' precisa ser um objeto: glob -> motivo.")
    for glob, reason in value.items():
        # `null` desliga um gatilho herdado do perfil.
        if reason is not None and not isinstance(reason, str):
            raise InvalidConfig(f"'{name}.{glob}' precisa ser texto ou null.")


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> None:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)


def _build(root: Path, d: dict[str, Any]) -> Config:
    memory_dir = d["memory_dir"].strip().strip("/\\") or "memory"
    return Config(
        root=root.resolve(),
        project=d["project"] or root.resolve().name,
        profile=d["profile"],
        memory_dir=memory_dir,
        index_files=tuple(d["index"]["files"]),
        stale_after_days=d["housekeeping"]["stale_after_days"],
        journal_after_days=d["housekeeping"]["journal_after_days"],
        proposal_after_days=d["housekeeping"]["proposal_after_days"],
        markers=tuple(d["housekeeping"]["markers"]),
        max_chars=d["briefing"]["max_chars"],
        guard_secrets=d["guard"]["secrets"],
        guard_memory_secrets=d["guard"]["memory_secrets"],
        human_decisions=d["guard"]["human_decisions"],
        guard_git_hooks=d["guard"]["git_hooks"],
        triggers={g: r for g, r in d["triggers"].items() if r},
        verify=tuple(d["verify"]),
    )

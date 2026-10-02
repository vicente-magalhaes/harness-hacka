"""Adaptador por agente: o mesmo hook atende Claude Code e Devin.

O núcleo (guard, aprovação, briefing, gatilhos) fala um dialeto só, o do Claude Code, onde o
harness nasceu. Este módulo traduz nas duas pontas: o evento que chega e a resposta que sai.
Agente novo é uma tabela aqui, não um `if` espalhado pelo guard.

O que o Devin manda de diferente (docs.devin.ai, hooks do CLI; ver a decisão 0002):

- ferramentas em minúsculas: `read`, `write`, `edit`, `apply_patch`, `notebook_edit`, `exec`;
- a chave do caminho nas ferramentas de arquivo não é documentada, então aceitamos as
  grafias comuns. `harness-hacka events` mostra as chaves que chegaram de verdade;
- bloqueio por `{"decision": "block", "reason": ...}` ou por saída 2 com o motivo no stderr.
  Fazemos os dois: a documentação descreve os dois e não diz qual vence;
- `DEVIN_PROJECT_DIR` no ambiente. É por ele que reconhecemos o Devin, porque o Devin também
  passa `CLAUDE_PROJECT_DIR` aos hooks no formato do Claude.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CLAUDE = "claude"
DEVIN = "devin"
AGENTS = (CLAUDE, DEVIN)

# Nome da ferramenta no agente -> nome canônico (o do Claude Code). `ApplyPatch` não existe no
# Claude: é o canônico de quem edita por patch, e o guard lê o patch em vez de `file_path`.
_TOOLS = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "notebook_edit": "NotebookEdit",
    "apply_patch": "ApplyPatch",
    "exec": "Bash",
}
_PATH_KEYS = ("file_path", "path", "filePath", "file", "target_file", "notebook_path")
_TEXT_ALIASES = {"old_str": "old_string", "new_str": "new_string", "contents": "content"}
_PATCH_KEYS = ("patch", "input", "diff", "content")

# Cabeçalhos dos dois formatos de patch que agentes usam: o do Codex (`*** Update File: x`) e o
# diff unificado (`+++ b/x`).
_PATCH_FILE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+?)\s*$")
_PATCH_MOVE = re.compile(r"^\*\*\* Move to: (.+?)\s*$")
_DIFF_OLD = re.compile(r"^--- (?:a/)?(.+?)\s*$")
_DIFF_NEW = re.compile(r"^\+\+\+ (?:b/)?(.+?)\s*$")
_NULL = "/dev/null"


def detect(env: Mapping[str, str] | None = None, explicit: str = "") -> str:
    if explicit in AGENTS:
        return explicit
    env = os.environ if env is None else env
    return DEVIN if env.get("DEVIN_PROJECT_DIR") else CLAUDE


def normalize(event: dict[str, Any]) -> dict[str, Any]:
    """O evento no dialeto do núcleo. Ferramenta que o núcleo não conhece passa como veio."""
    canonical = _TOOLS.get(str(event.get("tool_name", "")))
    if canonical is None:
        return event
    raw = event.get("tool_input")
    if not isinstance(raw, dict):
        return {**event, "tool_name": canonical}
    if canonical == "ApplyPatch":
        text = next((raw[k] for k in _PATCH_KEYS if isinstance(raw.get(k), str)), "")
        return {**event, "tool_name": canonical, "tool_input": {"patch": text}}
    tool_input = dict(raw)
    if "file_path" not in tool_input:
        for key in _PATH_KEYS:
            if tool_input.get(key):
                tool_input["file_path"] = tool_input[key]
                break
    for alias, name in _TEXT_ALIASES.items():
        if alias in tool_input and name not in tool_input:
            tool_input[name] = tool_input[alias]
    if canonical == "Edit" and isinstance(tool_input.get("edits"), list):
        canonical = "MultiEdit"
    return {**event, "tool_name": canonical, "tool_input": tool_input}


@dataclass
class FileChange:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    created: bool = False
    deleted: bool = False


def parse_patch(patch: str) -> dict[str, FileChange]:
    """Arquivos que o patch toca, com as linhas que entram e as que saem."""
    files: dict[str, FileChange] = {}
    current: FileChange | None = None
    old_name = ""
    for line in patch.splitlines():
        header = _PATCH_FILE.match(line)
        if header:
            kind, name = header.groups()
            current = files.setdefault(name, FileChange())
            current.created |= kind == "Add"
            current.deleted |= kind == "Delete"
            continue
        moved = _PATCH_MOVE.match(line)
        if moved:
            current = files.setdefault(moved.group(1), FileChange(created=True))
            continue
        if line.startswith("--- "):
            old = _DIFF_OLD.match(line)
            old_name = old.group(1) if old else ""
            continue
        if line.startswith("+++ "):
            new = _DIFF_NEW.match(line)
            name = new.group(1) if new else ""
            target = old_name if name == _NULL else name
            current = files.setdefault(target, FileChange()) if target else None
            if current is not None:
                current.created |= old_name == _NULL
                current.deleted |= name == _NULL
            continue
        if current is None or line.startswith("***"):
            continue
        if line.startswith("+"):
            current.added.append(line[1:])
        elif line.startswith("-"):
            current.removed.append(line[1:])
    return files


def render(output: dict[str, Any] | None, agent: str) -> tuple[str, str, int]:
    """(stdout, stderr, código de saída) da resposta do núcleo, no formato do agente."""
    import json

    if not output:
        return "", "", 0
    specific = output.get("hookSpecificOutput") or {}
    if agent == DEVIN and specific.get("permissionDecision") == "deny":
        reason = str(specific.get("permissionDecisionReason", ""))
        return json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False), reason, 2
    return json.dumps(output, ensure_ascii=False), "", 0

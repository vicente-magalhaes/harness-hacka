"""Estado por sessão, na pasta temporária do sistema.

Fica fora do repositório de propósito: não pede entrada no .gitignore de ninguém e não muda
de lugar quando o plugin atualiza. Estado que some num reboot é aceitável, porque nenhuma
sessão sobrevive a um.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path

APPROVAL_TTL_S = 30 * 60


def _dir(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session or "") or "no-session"
    folder = Path(tempfile.gettempdir()) / "harness-hacka" / safe
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _read(path: Path) -> dict[str, float]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): float(v) for k, v in data.items()}
    except (OSError, ValueError, AttributeError):
        return {}


def record_approval(session: str, numbers: list[int], now: float | None = None) -> None:
    path = _dir(session) / "approvals.json"
    data = _read(path)
    for n in numbers:
        data[str(n)] = now if now is not None else time.time()
    path.write_text(json.dumps(data), encoding="utf-8")


def approvals(session: str, now: float | None = None) -> set[int]:
    """Decisões que uma pessoa aprovou nesta sessão, nos últimos 30 minutos."""
    now = now if now is not None else time.time()
    data = _read(_dir(session) / "approvals.json")
    return {int(n) for n, t in data.items() if now - t <= APPROVAL_TTL_S}


def first_time(session: str, key: str) -> bool:
    """`True` só na primeira chamada com esta chave nesta sessão."""
    path = _dir(session) / "notices.json"
    data = _read(path)
    if key in data:
        return False
    data[key] = time.time()
    path.write_text(json.dumps(data), encoding="utf-8")
    return True


def once_within(session: str, key: str, seconds: float, now: float | None = None) -> bool:
    """`True` se esta chave não apareceu nesta sessão nos últimos `seconds` segundos."""
    now = now if now is not None else time.time()
    path = _dir(session) / "recent.json"
    data = _read(path)
    if now - data.get(key, float("-inf")) <= seconds:
        return False
    data[key] = now
    path.write_text(json.dumps(data), encoding="utf-8")
    return True


# ----------------------------------------------------------------------------------------
# Formato dos eventos que chegaram. Serve para conferir o adaptador de um agente novo, cuja
# documentação não diz todas as chaves. Guarda só NOMES de chave: o conteúdo do evento pode ter
# código, comando ou segredo, e nada disso sai da sessão.

EVENTS_FILE = "events.jsonl"
_EVENTS_KEPT = 200
_ENV_SEEN = ("CLAUDE_PROJECT_DIR", "DEVIN_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "DEVIN_PLUGIN_ROOT")


def _events_path() -> Path:
    folder = Path(tempfile.gettempdir()) / "harness-hacka"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / EVENTS_FILE


def record_event(hook: str, agent: str, event: dict[str, object]) -> None:
    import os
    from datetime import datetime

    try:
        tool_input = event.get("tool_input")
        line = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "hook": hook,
            "agent": agent,
            "session": str(event.get("session_id", ""))[:12],
            "event_keys": sorted(event),
            "tool_name": str(event.get("tool_name", "")),
            "tool_input_keys": sorted(tool_input) if isinstance(tool_input, dict) else [],
            "source": str(event.get("source", "")),
            "env": [v for v in _ENV_SEEN if os.environ.get(v)],
        }
        path = _events_path()
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        lines = [*lines[-(_EVENTS_KEPT - 1) :], json.dumps(line, ensure_ascii=False)]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError):
        return  # registro de diagnóstico nunca atrapalha o hook


def recorded_events() -> list[dict[str, object]]:
    path = _events_path()
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result.append(json.loads(line))
        except ValueError:
            continue
    return result

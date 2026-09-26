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

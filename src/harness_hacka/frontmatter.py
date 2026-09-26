"""Frontmatter YAML mínimo, sem dependência.

Cobre o subconjunto que a memória usa: `chave: valor`, lista em linha (`[a, b]`), lista em
bloco (`- item`), aspas e comentário com `#`. Não é um parser de YAML e não finge ser: o que
foge disso vira texto, e o `check` reclama do campo que não fizer sentido.
"""

from __future__ import annotations

import re
from datetime import date

_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


class InvalidFrontmatter(ValueError):
    pass


def split(text: str) -> tuple[dict[str, object], str]:
    """Devolve (campos, corpo). Texto sem frontmatter devolve ({}, texto)."""
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    if lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fields = _parse_fields([line.rstrip("\r\n") for line in lines[1:i]])
            return fields, "".join(lines[i + 1 :])
    raise InvalidFrontmatter("frontmatter aberto com '---' e nunca fechado")


def _parse_fields(lines: list[str]) -> dict[str, object]:
    fields: dict[str, object] = {}
    list_key: str | None = None
    for raw in lines:
        line = _strip_comment(raw)
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s*(.*)$", line) or re.match(r"^-\s+(.*)$", line)
        if item and list_key is not None:
            target = fields[list_key]
            assert isinstance(target, list)
            target.append(_scalar(item.group(1)))
            continue
        match = _KEY.match(line)
        if not match:
            raise InvalidFrontmatter(f"linha fora do formato 'chave: valor': {raw.strip()}")
        key, value = match.group(1), match.group(2).strip()
        if value == "":
            fields[key] = []
            list_key = key
            continue
        list_key = None
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fields[key] = [_scalar(v) for v in inner.split(",")] if inner else []
        else:
            fields[key] = _scalar(value)
    return fields


def _strip_comment(line: str) -> str:
    quote: str | None = None
    for i, c in enumerate(line):
        if c in "\"'":
            quote = None if quote == c else (quote or c)
        elif c == "#" and quote is None and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def text(fields: dict[str, object], key: str) -> str:
    value = fields.get(key, "")
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value).strip()


def as_list(fields: dict[str, object], key: str) -> list[str]:
    value = fields.get(key, [])
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    value = str(value).strip()
    return [value] if value else []


def parse_date(value: object) -> date | None:
    """Aceita `2026-09-26` e `26/09/2026`. Qualquer outra coisa é `None`."""
    raw = str(value or "").strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return date.fromisoformat(raw)
        match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", raw)
        if match:
            day, month, year = (int(g) for g in match.groups())
            return date(year, month, day)
    except ValueError:
        return None
    return None


def set_field(markdown_text: str, key: str, value: str) -> str:
    """Define `chave: valor` no frontmatter, criando o bloco se faltar. Preserva o resto.

    Só para campo escalar: se a chave era uma lista em bloco, os itens ficariam soltos.
    """
    new_line = f"{key}: {value}"
    original = markdown_text.lstrip("﻿")
    if not original.startswith("---"):
        return f"---\n{new_line}\n---\n\n{original}"
    lines = original.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            for j in range(1, i):
                if re.match(rf"^{re.escape(key)}\s*:", lines[j]):
                    lines[j] = new_line
                    return "\n".join(lines)
            lines.insert(i, new_line)
            return "\n".join(lines)
    raise InvalidFrontmatter("frontmatter aberto com '---' e nunca fechado")

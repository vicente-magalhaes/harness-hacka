"""O que nunca entra na memória: segredo e dado pessoal.

Só padrões de alta precisão. Falso positivo é pior que cheque ausente: ensina o time a
ignorar o aviso. Por isso não há regra genérica do tipo "senha=": ela casaria com o nome da
variável escrito na documentação (`SENHA_DO_BANCO`) e reprovaria texto inocente.
"""

from __future__ import annotations

import re

SECRETS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token do GitHub", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_\w{40,})")),
    ("chave da Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("chave de API no formato sk-", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("chave da AWS", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("chave do Google", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("chave secreta do Supabase", re.compile(r"\bsb_secret_[A-Za-z0-9_-]{20,}")),
    ("token do Slack", re.compile(r"\bxox[abpors]-[A-Za-z0-9-]{10,}")),
    (
        "JWT (chaves antigas do Supabase têm esse formato)",
        re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}"),
    ),
)

PERSONAL_DATA: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
)


def find_secrets(text: str) -> list[str]:
    """Nomes dos tipos de segredo encontrados. Nunca devolve o valor."""
    return [name for name, pattern in SECRETS if pattern.search(text)]


def find_personal_data(text: str) -> list[str]:
    return [name for name, pattern in PERSONAL_DATA if pattern.search(text)]

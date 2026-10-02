# harness-hacka

Plugin do Claude Code (o Devin instala o mesmo) e CLI em Python (só biblioteca padrão) que
guarda a memória de um projeto no próprio repositório: notas, decisões e diário. Um
housekeeping com subagente limpa o que envelheceu, e a decisão humana é garantida por hook.
Este repositório usa o próprio harness.

Identificadores em inglês (comandos, status, chaves, pastas, código). Explicação em
português (mensagens, comentários, documentação).

## Regras invioláveis

- Não importar biblioteca de terceiro em `src/harness_hacka/`. Os hooks rodam com o `python`
  do PATH, fora de qualquer venv.
- Hook nunca derruba a sessão. Toda exceção vira aviso no stderr e saída 0.
- Sem `.claude/harness-hacka.json` na raiz, nenhum hook age. É o gate.
- O que exige uma pessoa é `deny` com liberação pelo prompt dela, nunca `ask`. O `ask` segue
  o modo da sessão e passa sozinho em modo automático.
- Política de projeto não entra em `src/`. Vem da config do projeto ou de um perfil.
- Memória não se apaga, se arquiva.
- Agente novo entra por `src/harness_hacka/agents.py`, que traduz evento e resposta. O guard
  e as outras ações falam um dialeto só (decisão 0002).
- Falso positivo em cheque ou no guard é defeito, não excesso de zelo. Ensina a ignorar.

## Como trabalhar aqui

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
python bin/harness-hacka.py check     # a memória deste repositório
claude plugin validate .             # manifestos do plugin
```

Para testar o plugin numa sessão de verdade sem instalar: `claude --plugin-dir .` a partir
de um projeto que tenha `.claude/harness-hacka.json`.

## Memória

Notas, decisões e diário em [`memory/`](memory/README.md). O início de sessão já traz o
resumo; leia a nota antes de mexer no assunto dela.

<!-- harness-hacka:index -->
| Arquivo | Conteúdo | Ler quando |
|---|---|---|
| [memory/lessons.md](memory/lessons.md) | O que já foi tentado e não funcionou, com a lição | antes de mexer em hook, no briefing, no guard ou no formato do journal |
<!-- /harness-hacka:index -->

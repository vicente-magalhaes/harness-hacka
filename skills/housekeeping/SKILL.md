---
name: housekeeping
description: Limpar a memória do projeto. O subagente inspector revisa o que venceu ou ficou provisório e propõe keep, update, promote, merge, archive ou ask, com evidência; a pessoa escolhe o que aplicar. Use quando o início de sessão apontar housekeeping pendente ou quando pedirem revisão ou limpeza da memória.
argument-hint: "[all]"
---

# Housekeeping da memória

`harness-hacka` é o CLI deste plugin. Se o shell não achar o comando, use
`python "${CLAUDE_PLUGIN_ROOT}/bin/harness-hacka.py"` (ou `python3`). Sem essa variável
(fora do Claude Code), use
`uvx --from git+https://github.com/vicente-magalhaes/harness-hacka harness-hacka`.

Três papéis, nesta ordem. O CLI acha os candidatos, sem LLM. O subagente `inspector` julga
cada um e não edita nada. A pessoa decide o que aplicar. Você aplica só o que ela aprovou.

## 1. Candidatos

```bash
harness-hacka status --json
```

Os candidatos estão em `housekeeping.candidates`: notas vencidas, registros antigos do
diário e propostas paradas. Com o argumento `all`, inclua as notas com marcadores de
provisório (`notes[].markers`), mesmo que não tenham vencido.

Sem candidatos: diga que a memória está em dia e pare.

## 2. Inspeção

Chame o subagente `harness-hacka:inspector` com a ferramenta Agent. Passe a lista de
candidatos com os motivos, a pasta da memória, os marcadores da config e o que esta conversa
sabe de relevante sobre eles. Ele devolve um laudo: um item por candidato, com ação, motivo
e evidência.

Se o agente não tem subagente (o Devin na nuvem não carrega o do plugin), faça você a
inspeção com as mesmas regras: só leia, uma ação por candidato, evidência obrigatória
(`arquivo:linha`, commit ou trecho) e, sem evidência, a ação é `ask`. Nada se edita antes
do passo 3.

## 3. A pessoa decide

Mostre o laudo numerado e curto:

```
1. memory/06-prd-e-stack.md → update
   A nota diz que o banco está em aberto; 05 registra D-12 (Supabase). Evidência: 05:21.
2. memory/journal/2026-09-19-1400-busca.md → promote e archive
   A lição sobre busca por palavra-chave vai para memory/lessons.md.
3. memory/03-evidencias.md → keep até 2026-10-10
   Ainda é a única fonte das entrevistas.
```

Pergunte quais aplicar: "todos", "1 e 3" ou "nenhum". Item `ask` do laudo vira pergunta
direta para a pessoa, uma por vez.

## 4. Aplicar só o aprovado

- **keep**: troque `review_by` pela data proposta.
- **update**: edite só o trecho indicado, com o texto do laudo.
- **promote**: leve o conteúdo ao destino (nota existente, `lessons.md` com `type: lessons`,
  ou `/harness-hacka:decide` se for decisão, que nasce `proposed`). Depois arquive a origem.
- **merge**: junte na nota que fica e arquive a outra.
- **archive**: `harness-hacka archive <caminho> --reason "<motivo do laudo>"`. Nunca `rm`: o
  guard nega.

Decisão não se arquiva nem muda de status no housekeeping. Status de decisão é com a pessoa,
pelo `/harness-hacka:decide`.

Link que apontava para o que foi arquivado quebra, e o check acusa. Conserte apontando para
a nota que vale agora.

## 5. Registrar o housekeeping

```bash
harness-hacka new housekeeping
```

Preencha: o que foi aplicado, o que a pessoa recusou, o que ficou pendente, e o antes e
depois com os números do status. É a trilha de quem aprovou o quê.

## 6. Fechar

```bash
harness-hacka index --update
harness-hacka check
harness-hacka status
```

O check precisa sair 0. Mostre o antes e o depois em duas linhas.

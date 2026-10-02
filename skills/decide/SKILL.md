---
name: decide
description: Registrar uma decisão de arquitetura ou de produto, com as opções descartadas e o porquê. Use ao adicionar dependência ou serviço, criar um padrão que outros arquivos vão seguir, escolher entre alternativas não óbvias ou contrariar uma decisão existente.
argument-hint: "[problema + escolha]"
---

# Registrar uma decisão

`harness-hacka` é o CLI deste plugin. Se o shell não achar o comando, use
`python "${CLAUDE_PLUGIN_ROOT}/bin/harness-hacka.py"` (ou `python3`). Sem essa variável
(fora do Claude Code), use
`uvx --from git+https://github.com/vicente-magalhaes/harness-hacka harness-hacka`.

Você escreve a proposta. Só uma pessoa aceita. Isso não depende de você lembrar: o guard do
harness nega qualquer edição que ponha `status: accepted` até a pessoa escrever
`accept NNNN` no chat.
Onde os hooks não rodam (o Devin na nuvem, por exemplo), não há guard, e a regra vale do
mesmo jeito: `accepted` só depois de a pessoa escrever `accept NNNN`.

## 1. Procurar antes de escrever

```bash
harness-hacka status --json
```

Abra as decisões vivas que tocam o assunto. Se uma já cobre, diga qual e pare. Se a nova
contraria uma `accepted`, é substituição: a nova declara `supersedes: [NNNN]`.

Confira no código o estado real (Grep), não o presumido.

## 2. Tirar a decisão da pessoa, uma pergunta por vez

Pergunte até ter:

- o gatilho: o fato que forçou a decisão agora;
- as opções reais, ao menos duas ("não fazer nada" conta quando é real);
- por que cada descartada foi descartada. É a parte mais valiosa: impede a ideia de voltar;
- quando revisitar: a condição concreta que invalida a decisão.

Uma pergunta por vez, sem formulário. "Não sei" é resposta que se registra.

## 3. Escrever

```bash
harness-hacka new decision "<problema + escolha, curto>"
```

Preencha o arquivo criado e apague as instruções entre chaves.

- `## Rule`: uma ou duas linhas no imperativo. É o que o início de sessão mostra.
- Específico e verificável: "Supabase na nuvem, um projeto só", não "um banco gerenciado".
- Deixe `status: proposed` e não preencha `decided_by`.

## 4. Pedir a decisão

Mostre em até seis linhas: a escolha, as descartadas com o porquê e o custo aceito. Termine
com:

> Para aceitar, responda `accept NNNN`. Para recusar, diga o motivo.

- Se a pessoa aceitar: `status: accepted` e `decided_by: <nome dela>`. Se substitui outra,
  na antiga: `status: superseded` e `superseded_by: [NNNN]`.
- Se recusar: `status: rejected`, com o motivo no corpo. Proposta recusada também é memória.

## 5. Conferir

```bash
harness-hacka index --update
harness-hacka check
```

## Quando não é decisão

Bugfix, refatoração local, algo reversível em minutos, implementação de algo já decidido.
Isso vai no journal, ou em lugar nenhum.

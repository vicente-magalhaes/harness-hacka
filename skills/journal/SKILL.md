---
name: journal
description: Registrar esta sessão no diário antes de sair, com o contexto ainda cheio. O que mudou, o que não funcionou e o próximo passo. Use ao fim de qualquer sessão que mudou arquivo ou fez commit.
argument-hint: "[título do que mudou]"
---

# Registrar a sessão no journal

`harness-hacka` é o CLI deste plugin. Se o Bash não achar o comando, use
`python "${CLAUDE_PLUGIN_ROOT}/bin/harness-hacka.py"` (ou `python3`).

O registro é o que a próxima sessão recebe logo no início: os next steps e os dead ends.
Escreva você mesmo, agora. Um subagente não viu esta sessão.

Sessão sem mudança de estado (nenhum arquivo escrito, nenhum commit) não se registra. O
diário registra mudança, não presença.

## 1. Fatos, não lembrança

```bash
git status --short
git diff --stat
git log --oneline -10
```

Liste o que você de fato criou ou alterou nesta sessão.

## 2. Verificar antes de declarar

Rode as verificações do projeto quando fizerem sentido (o perfil sugere algumas, em
`verify`). Anote o resultado real, com número. Se algo falhou, o status é `partial` ou
`blocked`, nunca `done`.

## 3. Criar e preencher

```bash
harness-hacka new journal "<título imperativo do que mudou>"
```

Preencha o arquivo criado e apague as instruções entre chaves.

- Até ~25 linhas. Se precisa de mais, o conteúdo é decisão (`/harness-hacka:decide`) ou nota.
- Números, não adjetivos: "31 testes passando", não "testes ok".
- Cite decisões (`0003`) e requisitos (`RF-03`) quando houver.
- `## Dead ends`, um por linha, neste formato:
  `- {abordagem} → falhou porque {razão}. **Lesson:** {lição}`.
  É a seção de maior retorno: impede a próxima sessão de repetir o beco. Se não houve,
  `- none`.
- `## Next steps` em checklist, o mais importante primeiro.
- Sem segredo, token, URL interna ou dado pessoal.

Não edite registro antigo. Correção é registro novo que aponta o antigo.

## 4. Fechar

```bash
harness-hacka check
```

Precisa sair 0. Se a sessão revelou um fato que dura (não só o que aconteceu hoje), pergunte
se vale atualizar a nota certa agora ou deixar para o housekeeping.

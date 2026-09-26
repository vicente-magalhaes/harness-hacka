---
author: Vicente Magalhães (sessão com Claude)
status: partial
decisions: [0001]
---

# Criar o harness-hacka: núcleo, hooks, skills e inspector

## Changes

- Núcleo só com biblioteca padrão: config com gate, modelo da memória, auditoria, briefing
  com teto, índice gerado e arquivamento com `git mv`.
- Hooks `session-start`, `subagent-start`, `approval`, `guard` e `triggers`.
- Skills `init`, `journal`, `decide` e `housekeeping`; subagente `inspector`, só leitura.
- Perfis `python` e `nextjs`, README, CI em Windows e Linux, licença MIT.
- Nasceu como "zelador" (nomes em português); renomeado para "harness-itau" com
  identificadores em inglês e status do MADR; renomeado de novo para "harness-hacka" para
  não usar a marca do banco no nome do repositório, a pedido do Vicente.

## Why

Ver a 0001. A memória do time era só notas e uma tabela: faltava registro de sessão, trilha
de decisão, limpeza do que envelhece e decisão humana garantida.

## Dead ends

- Testar hooks com um comando que cita o arquivo de variáveis de ambiente → o hook de
  segredos do projeto hospedeiro barrou o próprio teste. **Lesson:** evento de teste vai num
  arquivo ou na suíte, não no comando.
- Teste de corte do briefing supondo "lição mais nova" dentro de um registro → não existe
  essa ordem; o corte respeita a ordem escrita. **Lesson:** teste de ordem usa registros de
  datas diferentes.
- Renomear a pasta do repositório com `mv` no Windows → a pasta estava vigiada pelas sessões
  do Claude Code no VS Code e o sistema recusou. **Lesson:** crie a pasta nova e copie; não
  mate processo para destravar.

## Verification

- 114 testes passando (`uv run pytest`), ruff limpo, `claude plugin validate .` aprovado.
- Sessões reais com `claude --plugin-dir`, já com os nomes novos: briefing injetado; Read de
  `id_rsa` negado pelo guard; aceite sem pessoa negado em `acceptEdits`; `accept 0004`
  liberou; `harness-hacka` no PATH do Bash.
- Na versão anterior (mesma lógica), o housekeeping chamou o inspector numa cópia da memória
  do hacka-itau e devolveu 4 keep com evidência. Prévia refeita no formato novo: índice
  gerado idêntico ao escrito à mão, 0 erros.

## Next steps

- [ ] Vicente decide a 0001
- [ ] Confirmar com a organização do hackathon se o harness conta como elemento
      pré-existente (regulamento cede ao Itaú o código feito durante o evento)
- [ ] Vicente cria o repositório público no GitHub e passa o link; eu configuro remote,
      primeiro commit e push
- [ ] Ligar no hacka-itau: frontmatter nas notas, região do índice e settings do time

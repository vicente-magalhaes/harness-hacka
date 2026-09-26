# Decisões

Uma decisão por arquivo, `NNNN-titulo.md`. Crie com `/harness-hacka:decide`. Os status
seguem o MADR.

<!-- harness-hacka:decisions -->
| Decisão | Título | Status |
|---|---|---|
| [0001](0001-harness-proprio-em-repositorio-separado.md) | Harness próprio, em repositório separado, distribuído como plugin | proposed |
<!-- /harness-hacka:decisions -->

| Status | Quer dizer |
|---|---|
| `proposed` | Escrita, esperando uma pessoa. Ainda não vale. |
| `accepted` | Vale. Tem `decided_by`. |
| `rejected` | Proposta que a pessoa recusou. Fica como registro do porquê. |
| `deprecated` | Valia e deixou de valer, sem nada no lugar. |
| `superseded` | Não siga. `superseded_by` diz qual vale no lugar. |

Regras:

1. Só uma pessoa aceita. O agente escreve a proposta; a pessoa responde `accept NNNN` no
   chat e só então a mudança de status passa pelo guard.
2. Corpo de decisão `accepted` não se reescreve. Mudou de ideia: nova decisão com
   `supersedes: [NNNN]`, e a antiga ganha `status: superseded` e `superseded_by`.
3. Opção descartada sempre com o porquê. É o que impede a ideia de voltar.

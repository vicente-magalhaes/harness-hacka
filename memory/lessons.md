---
type: lessons
read_when: antes de mexer em hook, no briefing, no guard ou no formato do journal
summary: O que já foi tentado e não funcionou, com a lição
review_by: 2026-11-10
---

# Lições

O que já foi tentado e não funcionou. O início de sessão injeta estes itens. Acrescente no
fim: o mais novo aparece primeiro.

- Pedir `ask` no guard para aceitar decisão → falhou porque o `ask` segue o modo da sessão e
  passa sozinho em modo automático. **Lesson:** o que exige pessoa é `deny`, liberado só pelo
  texto que ela digita (hook `UserPromptSubmit`).
- Contar o marcador `TODO` sem diferenciar maiúsculas → casa com a palavra "todo" em qualquer
  frase em português. **Lesson:** marcador conta com maiúsculas.
- Detectar CRLF depois de `read_text` → o Python converte o fim de linha na leitura.
  **Lesson:** para preservar CRLF, leia em bytes.
- Narrar a sessão por `claude -p` no hook `SessionEnd` → o hook de plugin tem cerca de 1,5 s
  (medido no harness-memoria). **Lesson:** registro narrado é skill, dentro da sessão.
- Bloco do início de sessão sem teto → acima de ~10.000 chars a plataforma troca o bloco por
  uma prévia (medido no harness-memoria). **Lesson:** orce o bloco e avise cada corte.
- Um arquivo de diário por mês com várias pessoas na mesma branch → conflito de merge no fim
  do arquivo a cada sessão. **Lesson:** um arquivo por registro.
- `python3` primeiro no comando do hook → no Windows pode ser o atalho da Microsoft Store,
  que não roda. **Lesson:** `python` primeiro, `python3` como reserva.
- Hook que cai na pasta atual quando `CLAUDE_PROJECT_DIR` não tem config → a política de
  outro projeto agiu (o teste do gate pegou). **Lesson:** quem diz qual é o projeto é a
  plataforma; a pasta atual só vale sem nenhuma indicação.
- Tratar a contagem de marcadores como veredito → a nota que descreve a convenção ("marcar
  [HIPÓTESE] no que não foi validado") conta como provisória (o inspector pegou, na prévia do
  hacka-itau). **Lesson:** marcador é pista para o inspector; quem julga é ele.

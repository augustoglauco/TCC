# Teste local — o agente escreve o código, o desenvolvedor testa

O Claude Code na nuvem não tem GPU, Ollama, Qdrant nem Postgres com os dados
reais. Além disso, a rede do container bloqueia o download de modelos do
Hugging Face, então ~17 testes do Qdrant e do MCP B2B falham lá mesmo com o
código certo. Por isso a validação de verdade roda **na máquina do
desenvolvedor**, e o resultado volta para o agente num arquivo só.

## O loop

1. **Agente:** implementa no branch de trabalho, faz push e diz qual suíte
   rodar (ex.: `--suite vendas`) e o que precisa ser confirmado.
2. **Você:** atualiza o código e sobe a aplicação como de costume
   (`goup.md`). O backend precisa logar em `/tmp/tcc-backend.log`, que já é o
   padrão do `goup.md`.

   ```bash
   git fetch origin && git checkout <branch> && git pull
   cd backend && uv sync --all-extras && uv run alembic upgrade head
   # reinicie o backend (goup.md §5) para carregar o código novo
   ```

3. **Você:** roda o roteiro, a partir de `backend/`:

   ```bash
   .venv/bin/python scripts/teste_local.py --suite vendas
   ```

   Opções úteis:
   - `--sem-pytest`: pula ruff + pytest e roda só os cenários de chat.
   - `--so V3`: roda só os cenários cujo nome começa com `V3`.
   - `--base-url` / `--log`: se o backend estiver em outra porta ou logando
     em outro arquivo.

   Não use o chat no navegador enquanto o roteiro roda. Os logs do backend
   hoje não carregam `conversation_id`, então o roteiro separa os logs de
   cada cenário pela posição no arquivo, e mensagens de outra origem
   entrariam no relatório.

4. **Você:** devolve o relatório gerado em
   `testes_locais/AAAAMMDD-HHMM-<suite>.md` de uma destas formas:
   - cola o conteúdo no chat com o agente; ou
   - commita e dá push no mesmo branch
     (`git add testes_locais && git commit -m "test: resultado local" && git push`),
     e o agente lê o arquivo de lá.

   A seção "Observações do testador", no fim do arquivo, é para o que você
   viu e o roteiro não captura: a cara da resposta no navegador, lentidão,
   algo estranho.

5. **Agente:** lê o relatório, corrige o que falhou e volta ao passo 1.

## O que o relatório contém

- **Checks automáticos:** resultado de `ruff check` e do `pytest` completo,
  com a lista de testes que falharam.
- **Cenários de chat:** para cada mensagem enviada a
  `POST /api/chat/messages`:
  - domínio, backend, motivo de escalonamento, modelo e `rag_retrieval_ms`
    (evento SSE `done`);
  - o texto completo da resposta;
  - as linhas de log do backend relevantes para a suíte.
- **Veredito automático:** só onde dá para decidir pelo log (ex.: em qual
  etapa a consulta de vendas parou e o que entrou no bloco do prompt).
  Cenários marcados como exploratórios têm veredito `—` e servem para
  observar o comportamento.

## Suítes disponíveis

| Suíte | O que cobre | Logs usados |
| --- | --- | --- |
| `vendas` | Integração do Orquestrador com o catálogo (R12, Fase 5): estoque, cotação com e sem desconto por volume, compatibilidade sim/não, produto inexistente, domínio que não é vendas e um cenário exploratório de conversa em duas mensagens | `vendas_catalogo_consulta` (campo `resultado`: `sem_termos`, `sem_candidatos`, `llm_sem_produto`, `produto_inexistente` ou `ok`, mais `termos`, `candidatos`, `slots` e o `bloco` injetado no prompt), `vendas_catalogo_consulta_falhou`, `rag_indisponivel` |

Os cenários de `vendas` assumem os dados semeados pelas migrações
`0003`/`0008`/`0009`: 5 produtos, 17 unidades de cada, desconto de 5% a
partir de 5 unidades e de 10% a partir de 10. Se você alterou o catálogo
local, os vereditos que conferem números podem falhar sem que o código esteja
errado. Nesse caso, anote nas observações.

Novas suítes entram no dicionário `SUITES` de `backend/scripts/teste_local.py`
e numa linha desta tabela, na mesma tarefa que implementa a funcionalidade.

`# MVP: roteiro de apoio ao teste manual, não avaliação experimental — a
avaliação do TCC continua em eval/ (docs/EVALUATION.md).`

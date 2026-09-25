# Teste local — o agente escreve o código, o desenvolvedor testa

O Claude Code na nuvem não tem GPU, Ollama, Qdrant nem Postgres com os dados
reais. Além disso, a rede do container bloqueia o download de modelos do
Hugging Face, então ~17 testes do Qdrant e do MCP B2B falham lá mesmo com o
código certo. Por isso a validação de verdade roda **na máquina do
desenvolvedor**, e o resultado volta para o agente num arquivo só.

## O loop

1. **Agente:** implementa no branch de trabalho, deixa o teste certo
   configurado (`SUITE_ATUAL` em `backend/scripts/teste_local.py`), faz push
   e pede "roda o teste".
2. **Você:** na raiz do repositório, roda:

   ```bash
   ./testar.sh
   ```

   Ele faz tudo sozinho:
   1. `git pull --rebase` (para se houver alteração local sem commit em
      arquivo versionado; arquivos soltos não atrapalham);
   2. `docker compose up -d`, `uv sync` e `alembic upgrade head`;
   3. confere se o Ollama responde;
   4. reinicia o backend (porta 8000, log em `/tmp/tcc-backend.log`) e o
      MCP B2B (porta 8100, log em `/tmp/tcc-mcp-b2b.log`), e inicia o Caddy
      (porta 8443) se ele não estiver no ar e estiver configurado;
   5. roda o roteiro (`ruff` + `pytest` + a suíte `SUITE_ATUAL`);
   6. faz commit e push do relatório em `testes_locais/`, atualizando e
      tentando de novo se o branch remoto mudou durante o teste.

   Pode usar o chat no navegador enquanto ele roda: cada linha de log do
   backend carrega o `conversation_id`, e o roteiro só pega as linhas das
   conversas dele.
3. **Você:** avisa o agente: "rodei o teste".
4. **Agente:** lê o relatório no branch, corrige o que falhou e volta ao
   passo 1.

**Primeira vez:** o `testar.sh` testa o branch em que você está. Antes da
primeira execução, entre no branch de trabalho do agente
(`git fetch origin && git checkout <branch>`).

Opções, repassadas ao roteiro: `./testar.sh --sem-pytest` pula ruff +
pytest; `./testar.sh --so V3` roda só um cenário; `./testar.sh --suite <nome>`
roda outra suíte.

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
| `vendas` | Integração do Orquestrador com o catálogo (R12, Fase 5): estoque, cotação com e sem desconto por volume, compatibilidade sim/não, produto inexistente, domínio que não é vendas e duas conversas de acompanhamento em que a 2ª mensagem não cita o produto (V8, V9) | `vendas_catalogo_consulta` (campo `resultado`: `sem_termos`, `sem_candidatos`, `llm_sem_produto`, `produto_inexistente` ou `ok`, mais `termos`, `termos_historico`, `candidatos`, `slots` e o `bloco` injetado no prompt), `vendas_catalogo_consulta_falhou`, `rag_indisponivel` |
| `mcp_b2b` | MCP B2B com chave por parceiro (R12, Fase 5, `docs/ARCHITECTURE.md` §6): M1/M2 `401` sem chave e com chave errada; M3 sessão MCP completa com a chave (`initialize`, as 4 ferramentas, `cotar`) e log com o nome do parceiro; M4 porta 8100 fechada para a rede; M5 Caddy local com o certificado do domínio (`curl --resolve`); M6 URL pública de dentro da rede (`—` se o roteador não tiver NAT loopback). Não chama `reservar_pedido`, que cria pedido de verdade. O teste de fora da rede é manual, com `scripts/cliente_mcp_b2b.py` (ver `goup.md`, "MCP B2B público") | `mcp_b2b_ferramenta` em `/tmp/tcc-mcp-b2b.log` |
| `memoria` | Memória da conversa e classificação do usuário (R9/R10, Fase 6, `docs/ARCHITECTURE.md` §5): R1 conversa gravada (4 mensagens pelo `GET /api/chat/conversations/{id}`); R2 resumo gerado em segundo plano (espera até 120 s) e usado na resposta seguinte; R3 pós-venda sem e-mail pede o e-mail; R4 a R7 perfil pelo e-mail da base fictícia (Ana = cliente, Bruno e Carla = esporádico, e-mail novo com intenção de compra = lead); R8 sem sinais; R9 e-mail lembrado entre mensagens. A retomada no widget é conferida à mão no navegador (instrução no fim do relatório) | `perfil_classificado`, `resumo_atualizado`, `resumo_falhou`, `memoria_indisponivel` |

Os cenários de `vendas` assumem os dados semeados pelas migrações
`0003`/`0008`/`0009`: 5 produtos, 17 unidades de cada, desconto de 5% a
partir de 5 unidades e de 10% a partir de 10. Se você alterou o catálogo
local, os vereditos que conferem números podem falhar sem que o código esteja
errado. Nesse caso, anote nas observações.

Novas suítes entram no dicionário `SUITES` de `backend/scripts/teste_local.py`
e numa linha desta tabela, na mesma tarefa que implementa a funcionalidade. O
agente aponta `SUITE_ATUAL` para a suíte que o próximo `./testar.sh` deve rodar.

`# MVP: roteiro de apoio ao teste manual, não avaliação experimental — a
avaliação do TCC continua em eval/ (docs/EVALUATION.md).`

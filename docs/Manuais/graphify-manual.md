# Manual Didático: Graphify no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)

Criado em 2026-10-14: das quatro ferramentas locais de inteligência de código,
o graphify era a única sem manual, embora seja a primeira consulta obrigatória
das três ferramentas agênticas (`CLAUDE.md`, seção "Graphify"). O papel dele
diante do GitNexus e do Repowise está em `docs/Manuais/gitnexus-manual.md` §2
e não é repetido aqui.

---

## 📌 1. O que é e o que ele entrega

Grafo estrutural do repositório extraído por AST — nós de arquivos, classes e
funções, chamadas diretas, comunidades (Louvain) e nós centrais. Não usa LLM
para extrair, então é rápido e sem custo de API.

Artefatos, todos versionados em `graphify-out/`:

| Arquivo                      | Para que serve                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------ |
| `graph.json`                 | O grafo em si; é o que a CLI consulta. ~3 MB.                                  |
| `graph.html`                 | Visualização interativa, servida pelo backend em `/admin/ferramentas`.         |
| `GRAPH_REPORT.md`            | Relatório macro: comunidades, god nodes, lacunas de conhecimento.              |
| `wiki/index.md`              | Navegação em prosa, quando existe — substitui ler código-fonte bruto.          |
| `.graphify_labels.json`      | Nomes das comunidades (ver §5, rotulagem).                                     |
| `manifest.json`              | Metadados do build (contagens, data).                                          |

---

## ⚡ 2. Comandos do dia a dia

```bash
# Orientação — sempre antes de abrir arquivo bruto
graphify query "<pergunta>"            # subgrafo enxuto do assunto
graphify query "<pergunta>" --budget 3000   # mais nós (o default trunca)
graphify explain "<símbolo/conceito>"  # um nó e seus vizinhos
graphify path "<A>" "<B>"              # dependência entre dois pontos

# Manutenção
graphify update .                      # re-extrai e atualiza (AST, sem LLM)
graphify update . --force              # aceita grafo menor (após deletar código)
graphify cluster-only .                # só reagrupa/renomeia comunidades
```

`explain` recusa nome ambíguo e lista os candidatos com o id completo — repita
o comando com o id ou o caminho relativo.

---

## 🔁 3. Atualização: hook desligado neste ambiente

O `graphify hook install` instala `.git/hooks/post-commit` e
`.git/hooks/post-checkout`, que rebuildam o grafo em background a cada commit
e a cada troca de branch.

**Esses hooks estão desativados aqui** (decisão de 2026-10-14): eles sujavam a
árvore de trabalho logo depois de cada commit, o que gerava commits de
*rebuild* em sequência e confundia o `git status` no meio de uma tarefa. O
rebuild passou a ser explícito — `graphify update .`, item 9 do checklist de
`docs/CONVENTIONS.md`.

O único opt-out que os hooks leem é a variável de ambiente, conferida nos dois
arquivos (`post-commit:27`, `post-checkout:47`):

```bash
export GRAPHIFY_SKIP_HOOK=1
```

Ela está no `~/.bashrc` da máquina de desenvolvimento. Três consequências que
valem saber:

- **O escopo é o shell, não o repositório.** Não há arquivo de configuração nem
  `git config` equivalente, e o projeto não usa `direnv`; logo, a variável vale
  para todos os repositórios daquele usuário que tenham hooks do graphify.
- **Sessão já aberta não pega a variável** — `~/.bashrc` é lido na
  inicialização do shell. Para garantir numa sessão antiga, prefixe o comando:
  `GRAPHIFY_SKIP_HOOK=1 git commit ...`.
- **Para desligar só neste repositório**, em vez da variável: tire o bit de
  execução dos dois hooks (`chmod -x .git/hooks/post-commit
  .git/hooks/post-checkout`) e remova o export do `~/.bashrc`. Um
  `graphify hook install` restaura os hooks.

---

## 🛠️ 4. Instalação e o cuidado com os arquivos de regras

`graphify install --platform claude` copia a skill, anexa um bloco de
instruções ao `CLAUDE.md` e instala hooks `PreToolUse` em
`.claude/settings.json`. **Leia `docs/CONVENTIONS.md`, seção "Ferramentas que
escrevem nos arquivos de regras", antes de rodar** — em 2026-10-14 essa
execução duplicou a seção "Graphify" do `CLAUDE.md` e cravou um caminho
absoluto (`/home/<usuário>/.local/bin/graphify`) num arquivo versionado que o
Antigravity e o Kiro também leem.

Hoje a seção fica entre `<!-- graphify:start -->` e `<!-- graphify:end -->`, e
os hooks `PreToolUse` moram em `.claude/settings.local.json` (não versionado).
Depois de qualquer instalação, rode `git status` e reverta o que não foi
pedido.

Os guards `PreToolUse` (`graphify hook-guard search` e `hook-guard read`) são
apenas **advisory**: saem com código 0 e injetam um lembrete no contexto do
agente, nunca bloqueiam a chamada.

---

## 🏷️ 5. Rotulagem de comunidades (sem chave de LLM)

Por padrão o `update`/`cluster-only` tenta nomear as comunidades com um LLM.
Sem `GEMINI_API_KEY` nem `GOOGLE_API_KEY` configuradas — o caso aqui — o
graphify avisa e mantém nomes derivados do nó central da comunidade (ex.:
`"useChatStore.ts"`, `"orchestrator.py"`), o que é suficiente para navegar.

Para pular a rotulagem de propósito: `graphify cluster-only . --no-label`.

O `cluster-only` é também o caminho para regerar o relatório sem re-extrair o
código. Os hooks exportam `PYTHONHASHSEED=0` porque o Louvain do networkx
itera conjuntos com chave de texto, cuja ordem muda por processo — sem o pin,
as comunidades trocam de número a cada build e o `graphify-out/` fica com
diff mesmo sem mudança de código.

---

## 🧩 6. Integração com o restante do projeto

- **Painel admin:** `/admin/ferramentas` mostra o status do graphify e serve o
  `graph.html`. O backend lê o arquivo direto (`_status_graphify` em
  `backend/src/app/api/admin_ferramentas.py`), reporta `graphify update .` como
  comando de atualização e considera a ferramenta "online" apenas se
  `graph.json` existir — ele **não** garante que o grafo esteja atualizado.
- **Arquivos de regras:** `CLAUDE.md` (seção "Graphify"),
  `.agents/rules/project.md` (regra 9) e `.kiro/steering/project.md` (regra 11)
  apontam para este fluxo. A ordem de uso em relação ao GitNexus está em
  `docs/CONVENTIONS.md`, "Ordem de uso dos dois grafos de código".
- **Limite conhecido:** o parser TSX do tree-sitter usado na extração falha em
  `&` literal dentro de texto JSX e em argumento após argumento de tipo
  quebrado em várias linhas. Isso aparece como arquivo faltando no grafo, não
  como erro. Histórico e correção em `docs/ROADMAP.md` (2026-10-14).

---

## 📋 7. Folha de cola

```bash
# Me oriente antes de eu abrir arquivo
graphify query "onde fica a validação de estoque do pedido"

# Quem é esse símbolo e com quem ele fala
graphify explain "handle_message"

# Como A chega em B
graphify path "ChatModal" "getApiBaseUrl"

# Depois de mexer no código (o hook não faz mais isso)
graphify update .

# Commit sem disparar hook, em sessão de shell antiga
GRAPHIFY_SKIP_HOOK=1 git commit -m "..."
```

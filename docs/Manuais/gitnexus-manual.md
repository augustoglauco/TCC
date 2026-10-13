# Manual Didático: GitNexus no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI)

O **GitNexus** é uma ferramenta avançada de inteligência de código e análise de grafos de conhecimento (*knowledge graph & code intelligence*). Ele analisa o repositório, mapeia símbolos (funções, classes, métodos, rotas), constrói um grafo de chamadas bidirecional, detecta fluxos de execução (*execution flows*), avalia riscos de raio de impacto (*blast radius*) antes de edições e fornece uma interface web rica e um servidor MCP (Model Context Protocol) para agentes de IA e desenvolvedores.

---

## 📌 1. Sumário de Recursos, Portas e Convivência no Ecossistema

O ambiente de desenvolvimento deste projeto combina múltiplos serviços e utilitários especializados. O GitNexus foi configurado para operar sem colisões de portas ou recursos:

| Ferramenta | Função no Projeto | Porta / Protocolo | Local de Dados / Executável |
| :--- | :--- | :--- | :--- |
| **GitNexus Web UI / HTTP** | Dashboard visual do grafo, fluxos e clusters | `4747` (ou porta dinâmica via `-p`) | Web UI SPA / Servidor local |
| **GitNexus MCP** | Contexto estrutural profundo e guardrails para agentes | `stdio` ou `/api/mcp` | Configurado nos agentes / `.mcp.json` |
| **GitNexus CLI / Engine** | Indexador AST, grafo KùzuDB/LadybugDB, análise de impacto | CLI local (`gitnexus` ou `node .gitnexus/run.cjs`) | Diretório `.gitnexus/` |
| **Repowise Web UI** | Dashboard gráfico para navegação na wiki | `7339` (ou dinâmico via `repowise serve`) | Cache local do frontend web |
| **Repowise MCP / CLI** | Wiki viva, triagem semântica, dead code e distill | `stdio` ou `7338` | Diretório `.repowise/` |
| **Graphify** | Grafo estático estrutural via AST (sem servidor) | CLI local (`graphify`) | `graphify-out/` (`graph.json`, `graph.html`) |
| **Headroom** | Proxy de compressão de contexto e histórico de LLM | `8787` (HTTP) | Wrapper `headroom wrap claude` |
| **Strata (Swift 1.5)** | Engine local de inferência MoE (CUDA / GPU) | `8080` (OpenAI `/v1` e Anthropic `/v1`) | `/home/augusto/Projetos/Strata` |
| **Ollama** | Servidor local de LLMs menores (7B–8B) | `11434` (HTTP) | Sistema |
| **OmniRoute** | Gateway unificado de roteamento de LLMs | `20128` (HTTP) | Sistema |

> [!NOTE]
> **Isolamento de Portas:** O GitNexus utiliza por padrão a porta `4747` para o servidor Web / HTTP. Essa porta não conflita com o Repowise (`7338`/`7339`), Strata (`8080`), Headroom (`8787`) ou Ollama (`11434`). Caso necessite rodar em outra porta, basta usar o parâmetro `-p <porta>`.

---

## 🔄 2. Convivência e Papéis: GitNexus vs. Repowise vs. Graphify

Cada ferramenta cobre uma camada específica do fluxo agêntico:

1. **Graphify (`graphify-out/`)**:
   - **Camada:** Grafo estático puramente estrutural baseado em AST (nós de classes/funções, chamadas diretas e comunidades Louvain).
   - **Propósito:** Inspeção rápida em arquivos locais sem custo de LLM nem servidores em execução.
2. **Repowise (`.repowise/`)**:
   - **Camada:** Semântica e documentação arquitetural (*living wiki*), busca híbrida, triagem contextual (`repowise context`), detecção de código órfão (`repowise dead-code`) e compactação de logs de ferramentas (`repowise distill`).
3. **GitNexus (`.gitnexus/`)**:
   - **Camada:** Grafo de execução profundo, call graph bidirecional, cadeias de taint (PDG) e **análise de impacto pré-edição (Blast Radius)**.
   - **Diferencial:** Possui ganchos ativos (hooks) que impedem o agente de editar código cego ou commitar quebras silenciosas em fluxos de execução encadeados.

---

## 🌐 3. Inicialização e Uso da Interface Web (`gitnexus serve`)

A interface web do GitNexus permite navegar visualmente por todos os símbolos, clusters funcionais e rastros de execução mapeados no projeto.

### 3.1 Inicialização Interativa (Primeiro Plano)

No terminal dentro da raiz do repositório (`/home/augusto/Projetos/TCC`):

```bash
# Porta padrão (4747)
npx gitnexus serve

# Ou utilizando o runner local do projeto:
node .gitnexus/run.cjs serve

# Se instalado globalmente (npm i -g gitnexus):
gitnexus serve
```

### 3.2 Inicialização com Porta Customizada ou Acesso em Rede

```bash
# Definindo uma porta específica (ex: 8091)
npx gitnexus serve -p 8091

# Permitindo acesso externo ou de outros dispositivos na rede local:
npx gitnexus serve -p 8091 --host 0.0.0.0
```

### 3.3 Inicialização em Segundo Plano (Background / Daemon)

Para manter o visualizador rodando sem ocupar o terminal ativo:

```bash
nohup npx gitnexus serve -p 4747 > /tmp/gitnexus-serve.log 2>&1 &
```

* Para verificar se está rodando:
  ```bash
  ps aux | grep "gitnexus serve"
  ```
* Para encerrar o processo em segundo plano:
  ```bash
  pkill -f "gitnexus serve"
  ```

### 3.4 Acesso no Navegador

Após iniciar o servidor, abra:
👉 **`http://localhost:4747`** *(ou na porta definida com `-p`)*

---

## ⚡ 4. Análise e Atualização do Índice (`gitnexus analyze`)

Para manter o grafo de conhecimento alinhado com o estado real do código:

### 4.1 Indexação Completa do Repositório

```bash
node .gitnexus/run.cjs analyze
# ou: npx gitnexus analyze
```

O comando realiza o parse das fontes (TypeScript/Next.js e Python/FastAPI), indexa classes, funções e chamadas no banco KùzuDB em `.gitnexus/` e atualiza os arquivos de diretrizes `AGENTS.md` e `CLAUDE.md`.

### 4.2 Flags Úteis do `analyze`

| Flag | Finalidade |
| :--- | :--- |
| `--watch` | Modo observador contínuo: reanalisa incrementalmente alterações salvas em arquivos. |
| `--force` | Força a reconstrução total do índice mesmo que o cache pareça recente. |
| `--index-only` | Atualiza somente o banco do grafo em `.gitnexus/`, sem alterar `AGENTS.md` ou `CLAUDE.md`. |
| `--pdg` | Constrói camadas de dependência de fluxo de dados/taint para análise de segurança. |
| `--embeddings` | Gera embeddings locais para habilitar busca semântica no grafo. |

### 4.3 Verificando a Saúde e Frescor do Índice

```bash
node .gitnexus/run.cjs status
```

Exibe o total de nós, arestas, data da última análise e se o repositório está atualizado.

---

## 🛡️ 5. Regras Críticas de Fluxo de Trabalho (Guardrails Agênticos)

As regras abaixo são estipuladas no arquivo de diretrizes agênticas (`AGENTS.md`) e devem ser respeitadas pelo desenvolvedor e por agentes de IA:

### ✅ Regras Obrigatórias (Always Do)

1. **Executar análise de impacto antes de editar:**
   - Antes de modificar uma função, método ou classe crítica, execute a checagem de impacto para ver quem depende dela:
     ```bash
     node .gitnexus/run.cjs impact "nomeDoSimbolo" --direction upstream --repo .
     ```
2. **Avaliar alterações no grafo antes de commitar:**
   - Valide se as modificações quebraram conexões ou processos:
     ```bash
     node .gitnexus/run.cjs detect-changes --scope all --repo .
     ```
3. **Avisar em riscos HIGH ou CRITICAL:**
   - Se o resultado do `impact` indicar risco alto ou crítico, planeje a migração e informe antes de aplicar a alteração.
4. **Tratar `risk: UNKNOWN` como não resolvido:**
   - Se o GitNexus reportar risco desconhecido, significa que chamadores dinâmicos ou de outra linguagem não foram resolvidos na AST estática. Confirme via busca de texto antes de assumir como seguro.

### ❌ Regras Proibitivas (Never Do)

1. **NUNCA** editar funções críticas sem análise prévia de impacto.
2. **NUNCA** ignorar alertas de risco HIGH/CRITICAL.
3. **NUNCA** renomear símbolos complexos usando apenas "Localizar e Substituir" global (use as ferramentas de refatoração do grafo ou revise todos os pontos detectados no `impact`).
4. **NUNCA** commitar mudanças sem rodar a verificação de alterações do GitNexus.

---

## 🛠️ 6. Comandos Práticos do Dia a Dia

### 6.1 Visão 360° de um Símbolo (`context`)

Apresenta chamadores (*callers*), chamados (*callees*) e processos de execução que utilizam o símbolo:

```bash
node .gitnexus/run.cjs context "criar_evento"
```

### 6.2 Análise de Raio de Impacto (*Blast Radius*) (`impact`)

Mostra tudo o que pode quebrar caso um determinado método ou função seja alterado:

```bash
# Quem consome este símbolo (upstream)
node .gitnexus/run.cjs impact "IntentRouter" --direction upstream

# O que este símbolo consome (downstream)
node .gitnexus/run.cjs impact "IntentRouter" --direction downstream
```

### 6.3 Menor Caminho entre Dois Símbolos (`trace`)

Mapeia a cadeia de chamadas entre um ponto A e um ponto B da aplicação:

```bash
node .gitnexus/run.cjs trace "login_endpoint" "verificar_token"
```

### 6.4 Busca de Fluxos por Conceito (`query`)

Encontra sequências e pipelines relacionados a uma intenção arquitetural:

```bash
node .gitnexus/run.cjs query "autenticacao e sessao"
```

### 6.5 Consultas Cypher Customizadas (`cypher`)

Permite rodar consultas diretas na linguagem Cypher sobre a base KùzuDB do GitNexus:

```bash
node .gitnexus/run.cjs cypher "MATCH (n:Function) WHERE n.name CONTAINS 'auth' RETURN n.name, n.file LIMIT 10"
```

### 6.6 Geração de Wiki Automatizada (`wiki`)

Gera documentação técnica estruturada a partir do grafo de conhecimento utilizando modelos locais ou remotos:

```bash
# Utilizando provider local ou de CLI existente
node .gitnexus/run.cjs wiki --lang pt-BR
```

---

## 🤖 7. Configuração e Integração com Agentes de IA

O utilitário `setup` conecta o GitNexus aos editores e ferramentas de IA instalados:

```bash
npx gitnexus setup
```

O comando configura automaticamente:
* **Antigravity IDE:** Registra MCP e skills de navegação em `.agents/skills/` e `~/.gemini/antigravity/skills/`.
* **Claude Code CLI:** Configura MCP e instala ganchos `PreToolUse` (aviso prévio de impacto) e `PostToolUse` (alerta de índice desatualizado após commits).
* **OpenCode / Codex:** Adiciona o servidor MCP aos respectivos arquivos de configuração.

---

## 📋 8. Folha de Cola Rápida (Cheat Sheet)

```bash
# 1. Iniciar a interface Web na porta padrão (4747)
npx gitnexus serve

# 2. Iniciar a interface Web em porta alternativa (ex: 8091)
npx gitnexus serve -p 8091

# 3. Reindexar o projeto após mudanças importantes
node .gitnexus/run.cjs analyze

# 4. Checar integridade e frescor do índice
node .gitnexus/run.cjs status

# 5. Avaliar risco de impacto antes de editar um símbolo
node .gitnexus/run.cjs impact "nomeDoMetodo" --direction upstream

# 6. Ver detalhes e conexões de um símbolo
node .gitnexus/run.cjs context "nomeDoMetodo"

# 7. Mapear o impacto das mudanças no git diff
node .gitnexus/run.cjs detect-changes --scope all

# 8. Limpar ou resetar o banco de dados do GitNexus
node .gitnexus/run.cjs clean --force
```

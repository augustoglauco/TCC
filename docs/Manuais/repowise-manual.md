# Manual Didático: Repowise no Ambiente de Desenvolvimento Agêntico (WSL2, Antigravity IDE, Claude CLI, Kiro CLI)

O **Repowise** é uma ferramenta de inteligência de código (*codebase intelligence*) projetada para fornecer contexto arquitetural profundo, documentação viva (*living wiki*), busca semântica, cartões de triagem de contexto, detecção de código morto e compactação de saídas para agentes de IA (Claude Code, Antigravity, Kiro) e desenvolvedores humanos.

---

## 📌 1. Sumário de Recursos, Portas e Convivência no Ecossistema

O ambiente de desenvolvimento deste projeto combina múltiplos serviços e utilitários especializados. O Repowise foi configurado para conviver de forma harmônica e sem conflitos de portas ou recursos:

| Ferramenta                   | Função no Projeto                                     | Porta / Protocolo                                    | Local de Dados / Executável                       |
| :--------------------------- | :------------------------------------------------------ | :--------------------------------------------------- | :------------------------------------------------- |
| **Repowise CLI**       | Inteligência de código, wiki viva, triage e dead code | CLI local (`~/.local/bin/repowise`)                | `.repowise/` (banco `wiki.db`, vetores)        |
| **Repowise MCP**       | Protocolo de contexto para agentes de IA                | `stdio` ou porta `7338` (Streamable HTTP / SSE)  | Configurado nos agentes /`.mcp.json`             |
| **Repowise Web UI**    | Dashboard gráfico para navegação na wiki             | `3002` (medido; o valor `7339` anunciado antes não confere) | Cache local do frontend web                        |
| **Graphify**           | Grafo de dependências estrutural via AST (estático)   | CLI local (`graphify`)                             | `graphify-out/` (`graph.json`, `graph.html`) |
| **Headroom**           | Proxy de compressão de contexto e histórico de LLM    | `8787` (HTTP)                                      | Local / Wrapper`headroom wrap claude`            |
| **Strata (Swift 1.5)** | Engine local de inferência MoE (CUDA / GPU)            | `8080` (OpenAI `/v1` e Anthropic `/v1`)        | `/home/augusto/Projetos/Strata`                  |
| **Ollama**             | Servidor local de LLMs menores (7B–8B)                 | `11434` (HTTP)                                     | Sistema                                            |
| **OmniRoute**          | Gateway unificado de roteamento de LLMs                 | `20128` (HTTP)                                     | Sistema                                            |

> [!NOTE]
> **Isolamento de Portas:** O Repowise opera por padrão via `stdio` ao se comunicar com agentes (sem ocupar portas de rede). Quando levantado em modo servidor de rede (`repowise mcp --transport streamable-http` ou `repowise serve`), utiliza as portas `7338` (MCP) e `3002` (Web UI). **Medido em 2026-10-13 nesta máquina: a Web UI sobe na `3002` (servidor Next.js), não na `7339` — só `3002` e `4747` estavam escutando. A tela `/admin/ferramentas` usa a `3002`; ajuste `REPOWISE_WEB_URL` se mudar.**
>
> **Atualização 2026-10-15 — porta pública na 3002:** a UI real sobe na `3012` e a `3002` é do Caddy (`infra/caddy/Caddyfile.ferramentas`, subido pelo `./g.sh`), com senha (usuário `admin`, `FERRAMENTAS_AUTH_HASH` em `infra/caddy/caddy.env`). Motivo: o iframe de `/admin/ferramentas` aponta para `localhost`, que de fora da rede (DuckDNS) é o computador do navegador; a tela troca host e porta pela pública quando o site não é aberto por `localhost`. À mão: `repowise serve --ui-port 3012` e `~/.local/bin/caddy run --config infra/caddy/Caddyfile.ferramentas --adapter caddyfile --envfile infra/caddy/caddy.env`.

---

## 🔄 2. Convivência e Uso Simultâneo com Outras Ferramentas

### 2.1 Repowise vs. Graphify: Como se Complementam?

Ambas as ferramentas lidam com grafos e conhecimento do código, mas em níveis complementares de abstração:

* **Graphify (`graphify-out/`)**:
  - *Foco:* Grafo puramente estrutural baseado em AST (classes, funções, imports, comunidades de Louvain).
  - *Custo:* Zero chamada a LLMs; processamento instantâneo em lote.
  - *Uso:* Mapeamento rápido de "quem chama quem", caminho mínimo (`graphify path`), subgrafo enxuto de dependências (`graphify query`).
* **Repowise (`.repowise/`)**:
  - *Foco:* Semântica e documentação arquitetural rica (*living wiki*), busca híbrida (vetorial + palavras-chave), triagem de módulos (`repowise context`), detecção de código órfão (`repowise dead-code`) e compactação de logs (`repowise distill`).
  - *Custo:* Análise semântica assistida por LLM (local ou remota).
  - *Isolamento:* Cada ferramenta armazena seus dados em diretórios distintos (`graphify-out/` vs `.repowise/`).

### 2.2 Repowise + Headroom: Economia de Tokens em Camadas

O Repowise e o Headroom atacam o desperdício de tokens em pontos diferentes do pipeline:

1. **Camada de Ferramentas / Shell (`repowise distill`):** Filtra a saída bruta e verbosa de comandos de terminal (como `pytest`, `npm test`, `git status` e buscas) antes que entrem no histórico do agente, compactando dados repetitivos e mantendo erros e resumos intactos.
2. **Camada de Transporte / Wire (`headroom wrap claude`):** Comprime o prompt completo e retém memória persistente entre sessões antes de enviar os dados à API da Anthropic.

> **Sinergia Perfeita:** Ao usar `headroom wrap claude`, o agente se beneficia da filtragem das ferramentas pelo Repowise e da compactação de chamadas pelo Headroom simultaneamente.

### 2.3 Repowise + Provedores Locais (Strata e Ollama)

Para gerar ou atualizar as páginas conceituais da wiki sem gastar créditos de APIs externas (como Anthropic ou OpenAI), o Repowise pode utilizar diretamente o **Ollama** ou um endpoint compatível:

```bash
# Inicialização usando o Ollama local (ex: Qwen 2.5 ou Llama 3.1)
repowise init --provider ollama --model gemma4:12b-it-q4_K_M --no-claude-md
```

---

## 🚀 3. Inicialização e Configuração Segura no Repositório

### ⚠️ Regra Crítica: Preservar o `CLAUDE.md` do Projeto

Neste repositório de TCC, o arquivo `CLAUDE.md` possui regras rígidas e consolidadas de escopo de MVP, checklist de commit e convenções agênticas. Ao rodar `repowise init`, **sempre utilize a flag `--no-claude-md`** para evitar que o gerador padrão sobrescreva as diretrizes do projeto.

> Isto não é específico do repowise: `graphify` e `gitnexus` também escrevem no `CLAUDE.md` e em `.claude/`. A regra geral — qual flag usar em cada instalador, o que é conteúdo gerado entre marcadores e por que hook com caminho absoluto não vai para arquivo versionado — está em `docs/CONVENTIONS.md`, seção "Ferramentas que escrevem nos arquivos de regras".

### 3.1 Inicialização Passo a Passo

Execute na raiz do projeto (`/home/augusto/Projetos/TCC`):

```bash
repowise init \
  --no-claude-md \
  --wiki-style comprehensive \
  --language pt-BR \
  --distill-hook
```

**O que este comando faz:**

1. Escaneia a árvore de código (backend FastAPI e frontend Next.js).
2. Constrói o banco vetorial e documental em `.repowise/wiki.db`.
3. Gera a coleção de Onboarding e arquitetura em português.
4. Preserva intacto o nosso `CLAUDE.md` oficial.
5. Habilita os ganchos do `distill` para compactar saídas no Claude Code.

### 3.2 Validação da Integridade do Setup

Após a inicialização, execute o diagnóstico do Repowise:

```bash
repowise doctor
```

O comando checará a presença do diretório `.repowise/`, a saúde do banco `wiki.db`, as integrações de agentes e o estado dos provedores de LLM.

---

## 🛠️ 4. Fluxos Práticos do Dia a Dia

### 4.1 Perguntas Semânticas sobre o Código (`repowise ask`)

Responde dúvidas arquiteturais apontando citações e arquivos exatos:

```bash
# Pergunta rápida com citações de código
repowise ask "Como funciona o fluxo do roteador de intenções entre local e externo?"

# Consulta focada em um módulo específico
repowise ask "Quais ferramentas o MCP B2B expõe para os parceiros?"
```

### 4.2 Cartão de Triagem de Arquivo ou Módulo (`repowise context`)

Antes de refatorar ou implementar mudanças, obtenha um resumo conciso de chamadores, dependências e métricas sem precisar ler milhares de linhas de código:

```bash
# Cartão de triagem de um arquivo do backend
repowise context backend/src/app/router/router.py

# Triagem incluindo skeleton e chamadores
repowise context backend/src/app/b2b.py --include callers --include callees
```

### 4.3 Detecção de Código Morto (`repowise dead-code`)

Detecta arquivos inacessíveis, funções exportadas que nunca são importadas e pacotes órfãos:

```bash
# Exibe apenas código morto com alta confiança de remoção segura
repowise dead-code --safe-only

# Varredura completa com saída formatada em tabela
repowise dead-code
```

### 4.4 Compactação de Comandos Ruidosos (`repowise distill`)

Executa testes ou buscas limpando ruídos e preservando apenas erros e sumários:

```bash
# Rodar testes automatizados sem poluir o terminal ou a janela do agente
repowise distill pytest backend/tests/unit -v

# Status do git ou build limpos
repowise distill git status
repowise distill npm --prefix frontend run build
```

> **Dica:** Se uma saída omitir algo que você precisa ver, use `repowise expand <ref>` com o identificador indicado pelo marcador.

### 4.5 Interface Gráfica da Wiki (`repowise serve`)

Inicia o visualizador web interativo para explorar a documentação e navegar nos tópicos da base de conhecimento:

```bash
repowise serve
```

Abra no navegador em `http://localhost:3002` — a lista de repositórios indexados — ou direto na visão geral deste repo: `http://localhost:3002/repos/98bf7b208ee54e9a840110278f8d9641/overview` (o id vem do índice local; confira a porta indicada no terminal).

---

## 🤖 5. Integração com Agentes de IA

### 5.1 No Claude Code CLI (`claude`)

O Repowise integra-se nativamente via MCP stdio ao Claude Code:

* Para listar agentes e configurações ativas:
  ```bash
  repowise agents
  ```
* Se precisar configurar explicitamente a integração:
  ```bash
  repowise agents add --target=claude-code
  ```
* Iniciando o Claude Code com o Headroom e o Repowise integrados:
  ```bash
  headroom wrap claude --memory
  ```

  *(Dentro da sessão, o Claude terá acesso às ferramentas do Repowise para pesquisar na wiki, ler skeletons e verificar dependências).*

### 5.2 No Antigravity IDE

Para adicionar o servidor MCP do Repowise às ferramentas do Antigravity, você pode cadastrá-lo em `~/.gemini/antigravity-ide/mcp/` ou conectar via transporte HTTP:

```bash
# Iniciar o servidor MCP na porta 7338 para conexões do IDE
repowise mcp --transport streamable-http --port 7338
```

Configuração de conexão no cliente MCP:

```json
{
  "mcpServers": {
    "repowise": {
      "command": "repowise",
      "args": ["mcp"]
    }
  }
}
```

### 5.3 No Kiro CLI

O Kiro CLI pode se conectar ao mesmo servidor MCP do repositório:

```bash
repowise agents add --target=kiro
```

---

## 🪝 6. Gerenciamento de Git Hooks e Atualizações

### Convivência no `post-commit`

O repositório já possui um hook `post-commit` que executa a atualização automática do **Graphify**.

* O hook de auto-sync do Repowise pode ser instalado com:
  ```bash
  repowise hook install
  ```
* O script de hook concatena de forma segura a rotina `repowise update` no `.git/hooks/post-commit`, mantendo a execução do Graphify e a do Repowise independentes.
* Para verificar o status dos hooks:
  ```bash
  repowise hook status
  ```
* Para desinstalar apenas o hook do Repowise mantendo os demais:
  ```bash
  repowise hook uninstall
  ```

---

## 📋 7. Folha de Cola Rápida (Cheat Sheet)

```bash
# 1. Inicializar no repositório preservando o CLAUDE.md oficial
repowise init --no-claude-md --wiki-style comprehensive --language pt-BR

# 2. Verificar a saúde da instalação
repowise doctor

# 3. Perguntar sobre a arquitetura
repowise ask "Onde estão definidos os contratos de API do backend com o frontend?"

# 4. Obter contexto de um arquivo antes de editá-lo
repowise context backend/src/app/router/router.py

# 5. Caçar código não utilizado antes de refatorar
repowise dead-code --safe-only

# 6. Rodar testes compactando a saída de ruído
repowise distill pytest

# 7. Subir a interface web de documentação
repowise serve

# 8. Atualizar a base após fazer alterações manuais no código
repowise update
```

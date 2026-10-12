# Manual Didático: Strata com Swift 1.5 no WSL2 (Antigravity IDE, Claude CLI, agy)

O **Strata** é uma engine de inferência CUDA de alto desempenho desenvolvida especificamente para modelos massivos Mixture-of-Experts (MoE) — neste ambiente, configurado com o modelo **Swift 1.5** (quantização `IQ3_XXS`, ~71 GB em shards GGUF e ~40 GB pack de especialistas), com speculative decoding (MTP) e cache dinâmico de experts.

O servidor expõe nativamente tanto a **API OpenAI** (`/v1/chat/completions`) quanto a **API Anthropic** (`/v1/messages`), além de uma interface web de chat e monitoramento.

---

## 📌 Sumário de Recursos e Portas

| Parâmetro | Detalhe no Ambiente |
| :--- | :--- |
| **Diretório do Strata** | `/home/augusto/Projetos/Strata` |
| **Binário CUDA Nativo** | `/home/augusto/Projetos/Strata/engine/strata` |
| **Pacote do Modelo** | `/home/augusto/Projetos/Strata-data/packs/swift-iq3_xxs` |
| **Porta Padrão** | `8080` (Livre — sem conflito com Ollama `11434`, OmniRoute `20128` ou Headroom `8787`) |
| **Consumo de Memória** | ~40 a 45 GB RAM e ~12 a 14 GB VRAM (RTX 4080 SUPER) quando o modelo está carregado |
| **Contexto Máximo** | `65.536` tokens (`--kv int8`) |

---

## 1. Como Iniciar o Strata

Você pode iniciar o servidor de três maneiras:

### Opção A: Primeiro Plano (Interativo — Recomendado para testes)
Mantenha o terminal aberto para acompanhar as métricas de geração e logs:

```bash
/home/augusto/Projetos/Strata/run-swift-iq3_xxs.sh
```

> **Para encerrar:** Pressione `Ctrl + C` no terminal.

---

### Opção B: Segundo Plano (Daemon / Background)
Inicia o servidor sem bloquear o terminal. Os logs são gravados em arquivo:

```bash
nohup /home/augusto/Projetos/Strata/run-swift-iq3_xxs.sh > /home/augusto/Projetos/Strata/strata.out 2>&1 &
```

* Para acompanhar os logs em tempo real:
  ```bash
  tail -f /home/augusto/Projetos/Strata/strata.out
  ```

---

### Opção C: Inicialização com Liberação Inteligente de Memória (Recomendado para o dia a dia)
O Strata possui duas flags avançadas que facilitam muito a convivência com outros projetos:

1. **`--lazy`**: Inicia o servidor HTTP instantaneamente, mas **não aloca** os 40 GB de RAM / 14 GB de VRAM até receber a primeira requisição real.
2. **`--idle-unload <segundos>`**: Descarrega o modelo da RAM e VRAM automaticamente após o tempo determinado de inatividade (ex: 300 segundos = 5 minutos) e **recarrega sozinho** quando uma nova requisição chegar.

```bash
cd /home/augusto/Projetos/Strata
nohup .venv/bin/python serve/server.py \
  --engine strata \
  --config strata-swift-iq3_xxs.json \
  --port 8080 \
  --lazy \
  --idle-unload 300 > strata.out 2>&1 &
```

---

## 2. Como Testar o Funcionamento

### 2.1 Verificar Saúde do Servidor (Health Check)
```bash
curl -s http://127.0.0.1:8080/health | jq .
```
*Resposta esperada:*
```json
{
  "status": "ok",
  "max_context": 65536,
  "model": "swift-1.5-iq3_xxs",
  "images": false,
  "api_key": false,
  "loaded": true,
  "service": "strata"
}
```

---

### 2.2 Listar Modelos Disponíveis
```bash
curl -s http://127.0.0.1:8080/v1/models | jq .
```

---

### 2.3 Testar Inferência — Dialeto OpenAI (`/v1/chat/completions`)
```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "swift-1.5-iq3_xxs",
    "messages": [
      {"role": "user", "content": "Olá! Responda em uma única frase quem é você."}
    ],
    "max_tokens": 50,
    "temperature": 0.7
  }' | jq .
```

---

### 2.4 Testar Inferência — Dialeto Anthropic (`/v1/messages`)
O Strata implementa nativamente o protocolo da Anthropic:
```bash
curl -s http://127.0.0.1:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: strata" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "swift-1.5-iq3_xxs",
    "messages": [
      {"role": "user", "content": "Diga 1, 2, 3 em português."}
    ],
    "max_tokens": 30
  }' | jq .
```

---

### 2.5 Testar via Interface Web (Navegador)
Abra no navegador (Windows ou WSL2):
👉 **`http://localhost:8080/`**

A interface web inclui chat interativo com streaming, visualização do consumo de tokens e status de carga do engine.

---

## 3. Como Usar no Claude CLI (`claude` / Claude Code)

Como o Strata implementa diretamente o endpoint Anthropic `/v1/messages`, a integração com o Claude CLI é direta e imediata.

### Método 3.1: Execução Direta no Terminal
Defina a URL base e uma chave fictícia para a sessão:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8080"
export ANTHROPIC_API_KEY="sk-strata-local"
claude
```

Ou em um único comando inline:
```bash
ANTHROPIC_BASE_URL="http://127.0.0.1:8080" ANTHROPIC_API_KEY="sk-strata-local" claude
```

> [!IMPORTANT]
> **Ajuste obrigatório para Claude Code (`fit_max_tokens`):**
> O Claude Code envia por padrão um teto alto de resposta (`max_tokens: 64000`). Como o contexto do modelo é `65536` e o histórico/prompt pode ter dezenas de milhares de tokens, a soma ultrapassa o contexto e o Strata retorna erro `400`.
> 
> Para corrigir automaticamente, adicione `"fit_max_tokens": true` no arquivo `strata-swift-iq3_xxs.json` ou a flag `--fit-max-tokens` no script de inicialização do Strata. Isso faz o Strata encurtar dinamicamente o `max_tokens` para o espaço restante no contexto em vez de rejeitar a requisição.

---

### Método 3.2: Combinado com o Headroom (Otimização de Contexto e Memória)
Se você utiliza o **Headroom** para comprimir contexto e reter memória entre sessões:

```bash
ANTHROPIC_BASE_URL="http://127.0.0.1:8080" ANTHROPIC_API_KEY="sk-strata-local" headroom wrap claude --memory
```

---

### Método 3.3: Via OmniRoute (Gateway Unificado)
Caso utilize o **OmniRoute** (já presente na porta `20128`), você pode cadastrar o Strata como um provedor customizado no painel do OmniRoute e gerar o perfil do Claude:
```bash
omniroute setup-claude
```

---

## 4. Como Usar no Antigravity IDE

Existem duas formas principais de integrar o Strata no Antigravity IDE:

### Forma 4.1: Conexão Direta OpenAI-Compatible (Via Configuração / Extensão de Chat)
Configure qualquer extensão de chat (como Continue, Codeium ou provedor local compatível com OpenAI):
* **Provider:** `openai` ou `openai-compatible`
* **API Base URL:** `http://127.0.0.1:8080/v1`
* **Model ID:** `swift-1.5-iq3_xxs`
* **API Key:** `sk-local` (ou qualquer texto não-vazio)

---

### Forma 4.2: Via Gateway OmniRoute
Como o Antigravity IDE e suas extensões podem se conectar ao `omniroute` local (`http://127.0.0.1:20128`), a rota do Strata (`http://127.0.0.1:8080/v1`) fica disponível para o IDE de forma transparente ao lado dos demais modelos configurados.

---

## 5. Como Usar com o Antigravity-CLI (`agy`)

O Antigravity-CLI (`agy`) gerencia sessões de terminal e suporta chamada direta a modelos configurados no ambiente:

### Modo 5.1: Execução de Prompts Não-Interativos (`--print` / `-p`)
```bash
OPENAI_BASE_URL="http://127.0.0.1:8080/v1" agy -p "Explique como funciona a arquitetura Mixture of Experts."
```

### Modo 5.2: Através do Gateway OmniRoute
Ao usar o OmniRoute como orquestrador padrão, defina o modelo do Strata no `settings.json` do CLI (`~/.gemini/antigravity-cli/settings.json`) ou passe via flag:
```bash
agy --model swift-1.5-iq3_xxs -i "Iniciar refatoração do backend"
```

---

## 6. Como Ligar e Desligar para Liberar Memória

O Swift 1.5 aloca cerca de **40 a 50 GB de RAM** e até **14 GB de VRAM da RTX 4080 SUPER**. Por isso, gerenciar o ciclo de vida do modelo é essencial quando você precisa rodar jogos, compilar código pesado ou rodar outros modelos no Ollama.

Existem dois níveis de liberação:

### 🟢 Nível 1: Hot Unload (Descarregar sem fechar o servidor — RECOMENDADO)
Este método libera **100% da VRAM e RAM** imediatamente, mantendo o processo HTTP ativo na porta 8080. O modelo pode ser recarregado a qualquer momento sem reiniciar scripts.

* **Para descarregar da memória (Liberar RAM e VRAM):**
  ```bash
  curl -s -X POST http://127.0.0.1:8080/v1/unload -H "Content-Type: application/json" -d '{}' | jq .
  ```

* **Para recarregar quando for usar novamente:**
  ```bash
  curl -s -X POST http://127.0.0.1:8080/v1/load -H "Content-Type: application/json" -d '{}' | jq .
  ```
  *(Ou simplesmente envie qualquer requisição de chat que o Strata recarrega automaticamente).*

---

### 🔴 Nível 2: Desligamento Completo do Servidor (Stop Total)

Se você iniciou em primeiro plano:
* Pressione **`Ctrl + C`** na janela do terminal.

Se iniciou em segundo plano (background):
* Execute o comando de encerramento de processos:
  ```bash
  pkill -f "serve.server.*strata"
  pkill -f "/home/augusto/Projetos/Strata/engine/strata"
  ```

* Para garantir que nada ficou preso:
  ```bash
  fuser -k 8080/tcp 2>/dev/null || true
  ```

---

### 🔍 Conferindo a Liberação da Memória

Após descarregar ou desligar, você pode validar o espaço recuperado:

* **Conferir VRAM da Placa de Vídeo:**
  ```bash
  nvidia-smi --query-gpu=memory.used,memory.free --format=csv
  ```
* **Conferir RAM do Sistema:**
  ```bash
  free -h
  ```

---

## 7. Folha de Cola Rápida (Cheat Sheet)

```bash
# 1. Iniciar em segundo plano com auto-unload após 5 min de inatividade:
cd /home/augusto/Projetos/Strata && nohup .venv/bin/python serve/server.py --engine strata --config strata-swift-iq3_xxs.json --port 8080 --lazy --idle-unload 300 > strata.out 2>&1 &

# 2. Testar se está online:
curl -s http://127.0.0.1:8080/health

# 3. Rodar Claude CLI com o Strata:
ANTHROPIC_BASE_URL="http://127.0.0.1:8080" ANTHROPIC_API_KEY="none" claude

# 4. Liberar RAM/VRAM imediatamente (sem matar servidor):
curl -s -X POST http://127.0.0.1:8080/v1/unload -H "Content-Type: application/json" -d '{}'

# 5. Encerrar completamente todos os processos:
pkill -f "serve.server.*strata"; pkill -f "/home/augusto/Projetos/Strata/engine/strata"
```

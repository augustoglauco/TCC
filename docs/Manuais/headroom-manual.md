# Manual Básico: Headroom com Claude CLI no IDE Antigravity

O **Headroom** é uma camada de otimização de contexto para aplicações LLM. Ele reduz o consumo de tokens e melhora o uso da janela de contexto ao intermediar as chamadas entre o **Claude CLI (`claude`)** e a API da Anthropic.

---

## 1. Modos de Uso

Existem três formas principais de integrar o Headroom ao seu fluxo de trabalho no IDE Antigravity:

### Método A: Uso Sob Demanda (Recomendado)
Inicia o proxy de otimização automaticamente em segundo plano apenas durante a execução daquela sessão do Claude CLI.

* **Comando padrão:**
  ```bash
  headroom wrap claude
  ```

* **Com ativação de memória persistente entre sessões:**
  ```bash
  headroom wrap claude --memory
  ```

* **Preservando a janela estendida de 1M tokens:**
  ```bash
  headroom wrap claude --1m
  ```

* **Passando flags nativas do Claude CLI (ex: resumir sessão):**
  ```bash
  headroom wrap claude --resume <session-id>
  ```

---

### Método B: Integração Permanente / Durável
Configura o Claude CLI globalmente para que **todas** as execuções passem pelo Headroom sem a necessidade de digitar `headroom wrap`.

* **Instalar a integração globalmente:**
  ```bash
  headroom init -g claude
  ```

* **Execução normal após configurado:**
  ```bash
  claude
  ```

---

### Método C: Proxy Manual em Segundo Plano
Ideal caso prefira manter o proxy ativo em uma aba separada do terminal ou serviço local.

1. **Iniciar o servidor proxy:**
   ```bash
   headroom proxy
   ```

2. **No terminal onde irá rodar o Claude CLI, exportar a URL do proxy:**
   ```bash
   export ANTHROPIC_BASE_URL="http://localhost:8787"
   claude
   ```

---

## 2. Como Desligar / Desativar

### Se ativou via Integração Permanente (`headroom init`)
Execute o comando de reversão para remover os hooks e desligar o proxy:
```bash
headroom unwrap claude
```

### Se ativou via `headroom wrap claude`
Basta encerrar a sessão do Claude CLI no terminal (digite `/exit` ou pressione `Ctrl + D`). O proxy temporário é encerrado junto com a sessão.

### Se usou o Proxy Manual
1. Remova a variável de ambiente:
   ```bash
   unset ANTHROPIC_BASE_URL
   ```
2. No terminal onde o `headroom proxy` está rodando, pressione **`Ctrl + C`**.

---

## 3. Monitoramento e Diagnósticos

| Comando | Descrição |
| :--- | :--- |
| `headroom dashboard` | Abre o painel visual no navegador para visualizar a economia de tokens em tempo real. |
| `headroom savings` | Exibe o total acumulado de tokens economizados via linha de comando. |
| `headroom doctor` | Valida se o proxy está ativo e se o roteamento está funcionando corretamente. |
| `headroom inspect` | Exibe o conteúdo original vs. o conteúdo comprimido enviado nas chamadas recentes. |

---

## 4. Resumo Rápido

```bash
#  Iniciar sessão rápida otimizada
headroom wrap claude --memory

#  Ver métricas de economia
headroom dashboard

# ❌ Desativar integração permanente
headroom unwrap claude
```

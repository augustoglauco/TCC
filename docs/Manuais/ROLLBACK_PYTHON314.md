# Procedimento de Rollback — Migração Python 3.14

Este documento descreve detalhadamente como desfazer a migração para o **Python 3.14** e retornar a aplicação e o ambiente de desenvolvimento para a versão anterior (**Python 3.13 / 3.11+**), caso seja necessário em qualquer momento.

---

## 1. Referências de Versão e Git

Antes da migração, uma tag de segurança foi criada no repositório local e remoto:

* **Tag Git Pré-Migração:** `pre-python314-baseline` (aponta para o commit `00bdaed`).
* **Commit com as Alterações de Código:** `2ee1dd2` (PEP 695 em `b2b.py`, PEP 649 em `models/` e `rag/`, `pyproject.toml`).
* **Commit de Sincronização do Lockfile:** `f4a4eff` (`backend/uv.lock`).
* **Commit de Merge na Master:** `5885d05`.

---

## 2. Opções de Rollback no Código (Git)

Escolha uma das duas opções abaixo, dependendo da necessidade:

### Opção A: Reversão Segura via `git revert` (Recomendada)
Mantém o histórico do Git intacto e cria um novo commit que desfaz exatamente as mudanças da migração:

```bash
# 1. Garanta que está na master e atualizado
git checkout master
git pull origin master

# 2. Reverte o commit de merge da migração
git revert -m 1 5885d05 -m "revert: rollback da migracao para Python 3.14"

# 3. Envia a reversão para o GitHub
git push origin master
```

---

### Opção B: Restauração Total para a Tag `pre-python314-baseline`

#### Para apenas inspecionar/rodar temporariamente na versão antiga:
```bash
git checkout pre-python314-baseline
```

#### Para forçar a branch `master` de volta ao estado exato anterior:
> [!WARNING]
> Isso reescreve o histórico da `master`. Use apenas se você realmente deseja descartar os commits da migração.
```bash
git checkout master
git reset --hard pre-python314-baseline
git push origin master --force
```

---

## 3. Rollback do Ambiente Virtual Local (`.venv`)

O código desfeito precisa do ambiente virtual compatível (Python 3.13 ou 3.11+). O `uv` reconstrói o ambiente em poucos segundos:

```bash
cd backend

# 1. Recria o .venv apontando para o Python 3.13 do sistema
uv venv --python 3.13 .venv --clear

# 2. Sincroniza todas as dependências da versão restaurada
uv sync --all-extras
```

---

## 4. Validação Pós-Rollback

Após aplicar o rollback no Git e recriar o `.venv`:

1. **Confira a versão do Python no ambiente:**
   ```bash
   cd backend
   .venv/bin/python --version
   # Deve exibir: Python 3.13.x
   ```

2. **Rode os testes automatizados:**
   ```bash
   .venv/bin/pytest -m "not gpu and not qdrant"
   # Esperado: 602 passed
   ```

3. **Reinicie os serviços do backend com o novo `.venv`:**
   ```bash
   # Derruba processos antigos nas portas 8000 e 8100
   fuser -k 8000/tcp 2>/dev/null || true
   fuser -k 8100/tcp 2>/dev/null || true
   sleep 1

   # Sobe o backend
   nohup .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > /tmp/tcc-backend.log 2>&1 &

   # Sobe o MCP B2B
   nohup .venv/bin/python scripts/run_mcp_b2b_server.py > /tmp/tcc-mcp-b2b.log 2>&1 &
   ```

4. **Verifique se responderam:**
   ```bash
   curl -s http://localhost:8000/docs >/dev/null && echo "Backend OK"
   curl -s http://127.0.0.1:8100/mcp >/dev/null && echo "MCP B2B OK"
   ```

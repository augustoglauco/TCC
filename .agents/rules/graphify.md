---
trigger: model_decision
description: Mapa macro opcional do código via graphify (graphify-out/, não versionado). Fonte única para código é o Repowise.
---

## graphify (opcional)

- O Repowise é a fonte única para perguntas de código; o graphify é só um mapa macro opcional (decisão de 2026-10-17, `docs/CONVENTIONS.md`, "Ordem de uso das ferramentas de grafo de código").
- `graphify-out/` não é versionado (2026-10-28): se não existir, rode `graphify update .` ou ignore. Nunca consulte antes de `grep`/leitura do arquivo.
- Use `graphify query|path|explain` só para visão macro de arquitetura ou para cruzar código com material não-código.

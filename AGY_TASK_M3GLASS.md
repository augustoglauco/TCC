# Tarefa Antigravity CLI: Conclusão da Refatoração Visual (M3 Glass)

Este arquivo contém todas as instruções, contexto, decisões de arquitetura e o estado exato para dar continuidade e concluir a refatoração visual do portal no **Antigravity CLI** (`agy`).

---

## 1. Contexto & Objetivo
- **Objetivo:** Refatorar a aparência visual do portal público com base no design industrial, moderno e responsivo do site da **M3 Glass** (`https://www.m3glass.com/`), usando imagens reais de equipamentos da **Control iD** (`docs/Manuais_fornecedor/ControlId/`).
- **Marca:** Mantida como `"Empresa Fictícia"` (com subtítulo *"Sistemas de Controle de Acesso & Segurança"*).
- **Viewports Obrigatórios:**
  - **Desktop:** $\ge 1024\text{px}$
  - **Smartphone:** $360\text{px} - 430\text{px}$
  - **Tablet 7 polegadas:** $600\text{px} - 800\text{px}$ (ex.: $600\times 1024$ ou $800\times 1280$)
- **Documentos de Referência:**
  - Spec oficial: `docs/superpowers/specs/2026-10-17-m3glass-visual-refactor-design.md` (commit `8f8ec1a`)
  - Plano oficial: `docs/superpowers/plans/2026-10-17-m3glass-visual-refactor.md` (commit `7eebebb`)

---

## 2. ⚠️ FRONTEIRA CRÍTICA DE ARQUITETURA (NUNCA VIOLAR)
- **`frontend/lib/utils/resolveImageUrl.ts` NUNCA DEVE SER ALTERADO PARA FAZER MATCH LOCAL POR NOME DE PRODUTO.**
  - **Motivo:** O card de produto do chat (`frontend/components/chat/cards/ProductCard.tsx`) importa essa função. Se ela sobrescrever imagens por nome, uma identificação errônea de produto via CLIP (Requisito R6) seria mascarada por uma imagem estática injetada, invalidando o dataset de teste de 107 imagens da Fase 10 (`docs/EVALUATION.md`).
  - Além disso, o catálogo `/produtos` deve refletir fielmente o banco de dados PostgreSQL/Qdrant. Se um produto do banco não tem foto cadastrada, deve exibir honestamente *"Sem foto cadastrada"*.
  - As fotos locais da Control iD em `frontend/public/images/showcase/` destinam-se **exclusivamente** à composição editorial e estática da Home (`HeroSlider`, `HardwareReveal`).

---

## 3. Estado Atual: O Que Já Está Pronto e Commitado
1. **Fase 2 (Header & Footer Industriais)** — Commit `4dabe10`:
   - `frontend/components/layout/Header.tsx`: Header escuro semitranslúcido com telefone de contato e botão para abrir o chat de IA.
   - `frontend/components/layout/Footer.tsx`: Footer industrial em 4 colunas.
   - Teste: `frontend/tests/unit/LayoutHeaderFooter.test.tsx` (PASSANDO).
2. **Fase 3 (Hero Slider & Tech Marquee)** — Commit `e741d45`:
   - `frontend/components/home/HeroSlider.tsx`: Slider de 3 equipamentos com card flutuante `slider-element`.
   - `frontend/components/home/TechMarquee.tsx`: Ticker contínuo infinito com marcas/tecnologias.
   - Testes: `HeroSlider.test.tsx` e `TechMarquee.test.tsx` (PASSANDO).
3. **Fase 4 (Hardware Reveal & Capabilities Grid)** — Commit `b12d7da`:
   - `frontend/components/home/HardwareReveal.tsx`: Display 50/50 estilo M3 Glass com seletor 01-05 (hover no mouse e tap no mobile).
   - `frontend/components/home/CapabilitiesGrid.tsx`: 4 domínios de negócio com elevação e bordas sutis.
   - Testes: `HardwareReveal.test.tsx` e `CapabilitiesGrid.test.tsx` (PASSANDO).

---

## 4. O Que Você Deve Fazer (Tarefas Restantes)

### 📌 Tarefa 1: Implementar `MetricCounters.tsx` e `ProcessSteps.tsx` (Fase 5)
1. Criar `frontend/components/home/MetricCounters.tsx`:
   - Grid industrial com 4 métricas de alto impacto:
     - `99.9%` — Precisão em Reconhecimento Facial (Algoritmo Biométrico Neural)
     - `< 0.2s` — Velocidade de Leitura e Autenticação
     - `100%` — Conformidade Portaria 671 MTE & LGPD
     - `24/7` — Assistente de IA & RAG Local
   - Estilização escura com cards `bg-slate-900/80 border border-slate-800 rounded-2xl p-6`.
2. Criar `frontend/components/home/ProcessSteps.tsx`:
   - Linha do tempo de 4 passos com números `01` a `04`:
     - `01. Consulta Multimodal` (Texto, foto de placa ou áudio via Whisper)
     - `02. Roteamento Híbrido` (Decisão inteligente entre GPU local 16GB e modelo externo)
     - `03. Cotação MCP B2B` (Consulta de estoque em tempo real e reserva de lotes)
     - `04. Agendamento de Visita` (Sincronização instantânea com Google Calendar)
3. Criar os testes unitários:
   - `frontend/tests/unit/MetricCounters.test.tsx`
   - `frontend/tests/unit/ProcessSteps.test.tsx`

---

### 📌 Tarefa 2: Montar a Home Page Final (Fase 6)
1. Atualizar `frontend/app/page.tsx`:
   - Integrar na ordem correta:
     1. `<HeroSlider />` (Hero principal)
     2. `<TechMarquee />` (Ticker de tecnologias)
     3. `<CapabilitiesGrid />` (Domínios de atendimento)
     4. `<HardwareReveal />` (Display 50/50 de equipamentos)
     5. `<MetricCounters />` (Contadores de confiabilidade)
     6. `<ProcessSteps />` (Fluxo de trabalho 01 a 04)
   - Adicionar seção de CTA final com botões para abrir o chat (`useChatStore.getState().open()`) e navegar para `/produtos`.
2. Criar/atualizar teste unitário `frontend/tests/unit/HomePage.test.tsx` verificando que os componentes renderizam sem erros.

---

### 📌 Tarefa 3: Galeria Técnica do Catálogo de Produtos (Fase 7)
1. Atualizar `frontend/app/produtos/page.tsx`:
   - Cabeçalho estilo galeria técnica com gradiente sutil.
   - Barra de busca e filtros em **pílulas com rolagem horizontal touch** no mobile e tablet (`overflow-x-auto scrollbar-none`).
   - Grid de produtos responsivo:
     - Mobile (360px): 1 coluna
     - Tablet 7'' (600px-800px): 2 colunas
     - Desktop ($\ge 1024$px): 3 ou 4 colunas
   - Preservar rigorosamente a paginação server-side e o modal de zoom de imagens (`ImageZoomModal`).
2. Atualizar `frontend/components/products/ProductCard.tsx`:
   - Card técnico com badge de disponibilidade, especificações resumidas e botão de zoom de imagem.
   - Se o produto não tiver imagem vinda do backend, exibir card neutro com `"Sem foto cadastrada"` (NÃO usar imagem hardcoded).
3. Criar/atualizar teste unitário `frontend/tests/unit/ProductCard.test.tsx`.

---

### 📌 Tarefa 4: Validação & Verificação Final (Fase 8)
No diretório `frontend/`, executar:
```bash
npm run test
npx prettier --check .
npx eslint
```
Garantir que todos os testes passem (100% de sucesso) e sem erros de lint ou formatação.

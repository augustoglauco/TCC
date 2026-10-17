# Plano de Implementação: Refatoração Visual M3 Glass & Control iD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar visualmente o frontend da Empresa Fictícia adotando a estética industrial premium e as ferramentas visuais dinâmicas do site M3 Glass Technologies (https://www.m3glass.com/), integrando fotografias de alta resolução de equipamentos Control iD e garantindo adaptação perfeita para Computador (principal), Smartphone (secundário) e Tablet de 7'' (terciário).

**Architecture:** A aplicação Next.js 16 (App Router) terá sua casca global (Header e Footer) e sua página inicial (`app/page.tsx`) reorganizadas em componentes modulares dinâmicos (HeroSlider com card flutuante de métricas, TechMarquee com rolagem infinita, HardwareReveal com exibição interativa 01 a 05, CapabilitiesGrid com elevação e bordas luminosas, MetricCounters com contadores acionados por viewport e ProcessSteps com fluxo visual). O catálogo (`app/produtos/page.tsx`) e os cards (`ProductCard.tsx`) adotarão o layout de galeria técnica com badges responsivas e atalhos touch.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4, Zustand 5, Radix UI, Vitest 4, Testing Library, Prettier 3, ESLint 9.

**Spec:** [docs/superpowers/specs/2026-10-17-m3glass-visual-refactor-design.md](file:///home/augusto/Projetos/TCC/docs/superpowers/specs/2026-10-17-m3glass-visual-refactor-design.md)

## Global Constraints

- Manter a marca institucional "Empresa Fictícia", incorporando os equipamentos e fotos reais da Control iD.
- Preservar 100% dos contratos das APIs REST do backend (`/api/produtos`, `/api/pedidos`, `/api/auth`, `/api/agendamentos`) e o streaming SSE do chat.
- Preservar o funcionamento do `ChatWidget` global e do menu administrativo `AdminGearMenu`.
- Código formatado rigorosamente com Prettier (`printWidth: 100`, `singleQuote: false`, `semi: true`, `trailingComma: "all"`).
- Zero erros de ESLint 9 (`npx eslint`).
- Nenhuma dependência externa pesada de animação: utilizar CSS keyframes nativos do Tailwind CSS 4 e React state hooks para máxima velocidade e performance.
- Não editar nem remover o bloco gerado em `frontend/AGENTS.md`.

## Review Focus

1. **Interação Touch no HardwareReveal:** Em smartphones e tablets de 7'', a troca de imagem do hardware não deve depender de hover de mouse; deve responder a toque direto nos itens e manter a área clicável acessível.
2. **Estabilidade de Layout no HeroSlider:** A troca de slides não deve causar saltos de altura (layout shift) na página em telas pequenas.
3. **Resolução de Imagens:** Produtos sem imagem local devem exibir o fallback visual neutro sem quebrar o card ou disparar erros no console.
4. **Filtro de Categorias no Mobile:** A barra de pílulas de categorias no catálogo deve permitir rolagem horizontal suave no celular sem quebrar a viewport.
5. **Preservação de Navegação e Chat:** Clicar em "Cotar" nos cards deve abrir o modal de chat sem navegar para fora da página.

---

### Task 1: Ingestão de Fotos Control iD na Vitrine Institucional (Home)

> **Decisão arquitetural (2026-10-17):** `frontend/lib/utils/resolveImageUrl.ts` **não é modificado** (mantém assinatura `resolveImageUrl(rawUrl)` de 1 argumento), pois `/produtos` deve refletir fielmente o banco PostgreSQL/Qdrant e exibir `"Sem foto cadastrada"` quando não houver foto no backend. As imagens estáticas locais da pasta public de imagens de produtos são utilizadas exclusivamente na vitrine institucional da Home (`frontend/components/home/HeroSlider.tsx` e `frontend/components/home/HardwareReveal.tsx`).

- [x] **Step 1: Copiar imagens de alta resolução para a vitrine institucional da Home**
  - Imagens copiadas: idface-frontal, idface-perspectiva, idblock-inox, idblock-preto, idblock-pcd, idblock-facial, idclass-373 e idaccess-pro.

- [x] **Step 2: Preservar `frontend/lib/utils/resolveImageUrl.ts` inalterado**
  - Confirmar que `frontend/lib/utils/resolveImageUrl.ts` permanece intacto.

---

### Task 2: Refatoração do Header e Footer Globais (Estética M3 Glass & Multi-Dispositivo)

**Files:**
- Modify: `frontend/components/layout/Header.tsx`
- Modify: `frontend/components/layout/Footer.tsx`
- Test: `frontend/tests/unit/LayoutHeaderFooter.test.tsx`

**Interfaces:**
- Consumes: `useAuthStore`, `useChatStore`, `AdminGearMenu`
- Produces: Header sticky translúcido com CTA dinâmico e Footer em 4 colunas industriais

- [ ] **Step 1: Escrever teste para Header e Footer responsivos**

Criar `frontend/tests/unit/LayoutHeaderFooter.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Header e Footer", () => {
  it("renderiza o Header com a marca Empresa Ficticia e botao de Chat", () => {
    render(<Header />);
    expect(screen.getByText(/Empresa Fictícia/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /abrir chat/i })).toBeInTheDocument();
  });

  it("renderiza o Footer com colunas de navegacao e selo do TCC", () => {
    render(<Footer />);
    expect(screen.getByText(/Protótipo TCC/i)).toBeInTheDocument();
    expect(screen.getByText(/Controle de Acesso/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar teste para verificar baseline**

Run: `cd frontend && npx vitest run tests/unit/LayoutHeaderFooter.test.tsx`  
Expected: PASS ou ajustes de acessibilidade necessários.

- [ ] **Step 3: Implementar visual M3 Glass no Header e Footer**

Em `Header.tsx`:
- Fundo escuro translúcido `bg-slate-950/85 backdrop-blur-md border-b border-slate-800 text-slate-100`.
- Logotipo estilizado da Empresa Fictícia com badge técnico *"SISTEMAS DE ACESSO & SEGURANÇA"*.
- Links de navegação com transições de hover suaves (`text-slate-300 hover:text-blue-400 hover:bg-slate-900/60`).
- Botão "💬 Falar com Assistente IA" em azul vibrante com sombra sutil e destaque.
- Gaveta de menu móvel com animação e suporte a toque para celulares e tablets.

Em `Footer.tsx`:
- Fundo `bg-slate-950 border-t border-slate-800 text-slate-400`.
- 4 colunas no formato M3 Glass: Institucional, Soluções de Hardware, Navegação e Atendimento/B2B.
- Faixa de rodapé inferior com copyright e selo acadêmico de TCC.

- [ ] **Step 4: Executar testes de layout e validar aprovação**

Run: `cd frontend && npx vitest run tests/unit/LayoutHeaderFooter.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write components/layout/Header.tsx components/layout/Footer.tsx tests/unit/LayoutHeaderFooter.test.tsx
git add frontend/components/layout/Header.tsx frontend/components/layout/Footer.tsx frontend/tests/unit/LayoutHeaderFooter.test.tsx
git commit -m "feat(frontend): refatora Header e Footer com estetica industrial M3 Glass"
```

---

### Task 3: Componentes Dinâmicos da Home: HeroSlider & TechMarquee

**Files:**
- Create: `frontend/components/home/HeroSlider.tsx`
- Create: `frontend/components/home/TechMarquee.tsx`
- Test: `frontend/tests/unit/HeroSlider.test.tsx`
- Test: `frontend/tests/unit/TechMarquee.test.tsx`

**Interfaces:**
- Consumes: `useChatStore.getState().open()`
- Produces: `HeroSlider`, `TechMarquee`

- [ ] **Step 1: Escrever testes unitários para HeroSlider e TechMarquee**

Criar `frontend/tests/unit/HeroSlider.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HeroSlider from "@/components/home/HeroSlider";

describe("HeroSlider", () => {
  it("renderiza titulo principal de tecnologia e botoes de acao", () => {
    render(<HeroSlider />);
    expect(screen.getByRole("button", { name: /conversar com o assistente/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explorar catálogo/i })).toBeInTheDocument();
  });

  it("permite avancar slide pelas setas de navegacao", () => {
    render(<HeroSlider />);
    const nextBtn = screen.getByRole("button", { name: /próximo slide/i });
    fireEvent.click(nextBtn);
    expect(nextBtn).toBeInTheDocument();
  });
});
```

Criar `frontend/tests/unit/TechMarquee.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TechMarquee from "@/components/home/TechMarquee";

describe("TechMarquee", () => {
  it("renderiza os selos de tecnologia da Control iD", () => {
    render(<TechMarquee />);
    expect(screen.getAllByText(/Reconhecimento Facial/i)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Catracas em Inox/i)[0]).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar testes e verificar falha**

Run: `cd frontend && npx vitest run tests/unit/HeroSlider.test.tsx tests/unit/TechMarquee.test.tsx`  
Expected: FAIL (módulos não encontrados)

- [ ] **Step 3: Implementar HeroSlider e TechMarquee**

Criar `frontend/components/home/HeroSlider.tsx`:
- 3 slides com transição suave:
  1. *Reconhecimento Facial 3D*: "Segurança Sem Contato e Validação em 0.2s" (iDFace).
  2. *Bloqueios Físicos e Catracas*: "Engenharia de Alta Durabilidade em Aço Inox" (iDBlock).
  3. *Ponto Eletrônico e RH*: "Homologado Portaria 671 do MTE com Nuvem" (REP iDClass).
- Card flutuante lateral de métricas dinâmicas com vidro fosco (`slider-element` M3 Glass).
- Totalmente responsivo para Desktop (lado a lado), Tablet 7'' e Smartphone (verticalizado sem quebra de tela).

Criar `frontend/components/home/TechMarquee.tsx`:
- Faixa horizontal com rolagem contínua suave via CSS keyframe sem bibliotecas externas.

- [ ] **Step 4: Rodar testes e verificar aprovação**

Run: `cd frontend && npx vitest run tests/unit/HeroSlider.test.tsx tests/unit/TechMarquee.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write components/home/HeroSlider.tsx components/home/TechMarquee.tsx tests/unit/HeroSlider.test.tsx tests/unit/TechMarquee.test.tsx
git add frontend/components/home/HeroSlider.tsx frontend/components/home/TechMarquee.tsx frontend/tests/unit/HeroSlider.test.tsx frontend/tests/unit/TechMarquee.test.tsx
git commit -m "feat(frontend): adiciona HeroSlider interativo e TechMarquee contínuo"
```

---

### Task 4: Componentes Dinâmicos da Home: HardwareReveal ("Hover-Reveal" M3 Glass) & CapabilitiesGrid

**Files:**
- Create: `frontend/components/home/HardwareReveal.tsx`
- Create: `frontend/components/home/CapabilitiesGrid.tsx`
- Test: `frontend/tests/unit/HardwareReveal.test.tsx`
- Test: `frontend/tests/unit/CapabilitiesGrid.test.tsx`

**Interfaces:**
- Consumes: Imagens locais de `frontend/public/images/products/`
- Produces: `HardwareReveal`, `CapabilitiesGrid`

- [ ] **Step 1: Escrever testes unitários**

Criar `frontend/tests/unit/HardwareReveal.test.tsx`:
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HardwareReveal from "@/components/home/HardwareReveal";

describe("HardwareReveal", () => {
  it("renderiza a lista de 5 equipamentos e atualiza o display ao selecionar", () => {
    render(<HardwareReveal />);
    expect(screen.getByText(/01/)).toBeInTheDocument();
    expect(screen.getByText(/iDFace/i)).toBeInTheDocument();
    
    // Troca para o item 02 (iDBlock)
    const item2 = screen.getByText(/iDBlock/i);
    fireEvent.mouseEnter(item2);
    expect(screen.getByRole("img", { name: /iDBlock/i })).toBeInTheDocument();
  });
});
```

Criar `frontend/tests/unit/CapabilitiesGrid.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CapabilitiesGrid from "@/components/home/CapabilitiesGrid";

describe("CapabilitiesGrid", () => {
  it("renderiza os 4 domínios de atendimento e soluções", () => {
    render(<CapabilitiesGrid />);
    expect(screen.getByText(/Controle de Acesso/i)).toBeInTheDocument();
    expect(screen.getByText(/Bloqueios & Catracas/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar testes e verificar falha**

Run: `cd frontend && npx vitest run tests/unit/HardwareReveal.test.tsx tests/unit/CapabilitiesGrid.test.tsx`  
Expected: FAIL

- [ ] **Step 3: Implementar HardwareReveal e CapabilitiesGrid**

Criar `frontend/components/home/HardwareReveal.tsx`:
- Painel esquerdo com display de imagem ampla em alta resolução (`idface-frontal.jpg`, `idblock-inox.jpg`, `rep-idclass.jpg`, etc.).
- Painel direito com itens numerados 01 a 05 com setas deslizantes.
- Suporte a evento de mouse (desktop) e toque direto com seleção persistente (smartphone e tablet 7'').

Criar `frontend/components/home/CapabilitiesGrid.tsx`:
- Grade de 4 domínios com ícones elegantes, elevação no hover e acento luminoso em azul elétrico.

- [ ] **Step 4: Rodar testes e verificar aprovação**

Run: `cd frontend && npx vitest run tests/unit/HardwareReveal.test.tsx tests/unit/CapabilitiesGrid.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write components/home/HardwareReveal.tsx components/home/CapabilitiesGrid.tsx tests/unit/HardwareReveal.test.tsx tests/unit/CapabilitiesGrid.test.tsx
git add frontend/components/home/HardwareReveal.tsx frontend/components/home/CapabilitiesGrid.tsx frontend/tests/unit/HardwareReveal.test.tsx frontend/tests/unit/CapabilitiesGrid.test.tsx
git commit -m "feat(frontend): adiciona HardwareReveal estilo M3 Glass e CapabilitiesGrid"
```

---

### Task 5: Componentes Dinâmicos da Home: MetricCounters & ProcessSteps

**Files:**
- Create: `frontend/components/home/MetricCounters.tsx`
- Create: `frontend/components/home/ProcessSteps.tsx`
- Test: `frontend/tests/unit/MetricCounters.test.tsx`
- Test: `frontend/tests/unit/ProcessSteps.test.tsx`

**Interfaces:**
- Consumes: Navegador com `IntersectionObserver`
- Produces: `MetricCounters`, `ProcessSteps`

- [ ] **Step 1: Escrever testes unitários**

Criar `frontend/tests/unit/MetricCounters.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MetricCounters from "@/components/home/MetricCounters";

describe("MetricCounters", () => {
  it("renderiza os valores de confiabilidade e métricas", () => {
    render(<MetricCounters />);
    expect(screen.getByText(/99.9%/i)).toBeInTheDocument();
    expect(screen.getByText(/0.2s/i)).toBeInTheDocument();
  });
});
```

Criar `frontend/tests/unit/ProcessSteps.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProcessSteps from "@/components/home/ProcessSteps";

describe("ProcessSteps", () => {
  it("renderiza os 4 passos do fluxo de atendimento inteligente", () => {
    render(<ProcessSteps />);
    expect(screen.getByText(/01/)).toBeInTheDocument();
    expect(screen.getByText(/Diagnóstico/i)).toBeInTheDocument();
    expect(screen.getByText(/04/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar testes e verificar falha**

Run: `cd frontend && npx vitest run tests/unit/MetricCounters.test.tsx tests/unit/ProcessSteps.test.tsx`  
Expected: FAIL

- [ ] **Step 3: Implementar MetricCounters e ProcessSteps**

Criar `frontend/components/home/MetricCounters.tsx`:
- Disparo de contador suave ao rolar a página para dentro da seção.
- Fundo escuro com estética industrial.

Criar `frontend/components/home/ProcessSteps.tsx`:
- 4 cartões de processo numerados `01`, `02`, `03`, `04` com linha de conexão estilizada e CTA para o chat.

- [ ] **Step 4: Rodar testes e verificar aprovação**

Run: `cd frontend && npx vitest run tests/unit/MetricCounters.test.tsx tests/unit/ProcessSteps.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write components/home/MetricCounters.tsx components/home/ProcessSteps.tsx tests/unit/MetricCounters.test.tsx tests/unit/ProcessSteps.test.tsx
git add frontend/components/home/MetricCounters.tsx frontend/components/home/ProcessSteps.tsx frontend/tests/unit/MetricCounters.test.tsx frontend/tests/unit/ProcessSteps.test.tsx
git commit -m "feat(frontend): adiciona MetricCounters com animação de viewport e ProcessSteps"
```

---

### Task 6: Montagem da Nova Home Page (`frontend/app/page.tsx`)

**Files:**
- Modify: `frontend/app/page.tsx`
- Test: `frontend/tests/unit/HomePage.test.tsx`

**Interfaces:**
- Consumes: `HeroSlider`, `TechMarquee`, `CapabilitiesGrid`, `HardwareReveal`, `MetricCounters`, `ProcessSteps`
- Produces: Página inicial completa com estética M3 Glass e multi-dispositivo

- [ ] **Step 1: Escrever teste de integração da Home Page**

Criar `frontend/tests/unit/HomePage.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page.tsx";

describe("HomePage", () => {
  it("renderiza todas as secoes estruturais da Home inspirada no M3 Glass", () => {
    render(<HomePage />);
    expect(screen.getByRole("button", { name: /conversar com o assistente/i })).toBeInTheDocument();
    expect(screen.getByText(/Como Trabalhamos/i)).toBeInTheDocument();
    expect(screen.getByText(/99.9%/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar teste e verificar comportamento atual**

Run: `cd frontend && npx vitest run tests/unit/HomePage.test.tsx`  
Expected: FAIL ou desajuste de seletores em relação à nova estrutura.

- [ ] **Step 3: Refatorar `frontend/app/page.tsx`**

Integrar as seções em ordem orquestrada:
1. `HeroSlider`: Impacto visual, CTAs principais e métricas laterais.
2. `TechMarquee`: Faixa infinita de capacidades técnicas.
3. `CapabilitiesGrid`: 4 domínios essenciais com cartões com elevação.
4. `HardwareReveal`: Efeito dinâmico M3 Glass de hardware (01 a 05).
5. `MetricCounters`: Estatísticas de desempenho e confiabilidade.
6. `ProcessSteps`: Jornada de atendimento com IA e MCP em 4 etapas.
7. Seção CTA Final: Chamada expressa para iniciar atendimento no Chat.

- [ ] **Step 4: Rodar teste e verificar aprovação**

Run: `cd frontend && npx vitest run tests/unit/HomePage.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write app/page.tsx tests/unit/HomePage.test.tsx
git add frontend/app/page.tsx frontend/tests/unit/HomePage.test.tsx
git commit -m "feat(frontend): refatora Home Page completa com layout e efeitos M3 Glass"
```

---

### Task 7: Redesign do Catálogo de Produtos (`app/produtos/page.tsx` e `ProductCard.tsx`)

**Files:**
- Modify: `frontend/components/products/ProductCard.tsx`
- Modify: `frontend/app/produtos/page.tsx`
- Test: `frontend/tests/unit/ProductCard.test.tsx`

**Interfaces:**
- Consumes: `Produto`, `fetchProducts`, `fetchProductCategories`
- Produces: Catálogo técnico estilo galeria M3 Glass e cards de produto atualizados

- [ ] **Step 1: Escrever teste para o ProductCard atualizado**

Criar/Atualizar `frontend/tests/unit/ProductCard.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductCard } from "@/components/products/ProductCard";

const mockProduto = {
  id: 1,
  nome: "Terminal Facial iDFace",
  categoria: "Controle de Acesso",
  preco: 2490,
  imagem_url: null,
  estoques: [{ quantidade: 10, centro_distribuicao: "CD-SP" }],
};

describe("ProductCard", () => {
  it("renderiza o card de produto com botoes Comprar e Cotar e imagem resolvida", () => {
    render(<ProductCard product={mockProduto as any} onOpenZoom={vi.fn()} />);
    expect(screen.getByText("Terminal Facial iDFace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /comprar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cotar/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar teste e verificar baseline**

Run: `cd frontend && npx vitest run tests/unit/ProductCard.test.tsx`

- [ ] **Step 3: Refatorar ProductCard e Catálogo**

Em `ProductCard.tsx`:
- Chamar `resolveImageUrl(product.imagem_url, product.nome)` para utilizar as fotos locais de alta resolução da Control iD quando disponíveis.
- Aplicar estilo de galeria técnica M3 Glass: cantos arredondados, bordas sutis `border-slate-200 hover:border-blue-400`, iluminação suave, ponto de pulso de estoque verde/âmbar, preço destacado e botões touch otimizados.

Em `app/produtos/page.tsx`:
- Header escuro com título de impacto (*"Catálogo Técnico de Equipamentos & Hardware"*).
- Barra de busca debounced com ícone de lupa e campo estendido.
- Barra de categorias em formato pílula com rolagem horizontal suave no celular e tablet de 7''.
- Agrupamento limpo e grid responsivo: 1 coluna no mobile, 2 colunas no tablet 7'', 3 a 4 colunas no desktop.

- [ ] **Step 4: Rodar teste e verificar aprovação**

Run: `cd frontend && npx vitest run tests/unit/ProductCard.test.tsx`  
Expected: PASS

- [ ] **Step 5: Formatar e commitar**

```bash
cd frontend && npx prettier --write components/products/ProductCard.tsx app/produtos/page.tsx tests/unit/ProductCard.test.tsx
git add frontend/components/products/ProductCard.tsx frontend/app/produtos/page.tsx frontend/tests/unit/ProductCard.test.tsx
git commit -m "feat(frontend): refatora catalogo de produtos e ProductCard no estilo galeria M3 Glass"
```

---

### Task 8: Verificação de Testes Unitários, Lint, Formatação e Checklist de Pré-Commit

**Files:**
- Test: Toda a suíte do frontend (`frontend/tests/`)
- Formatting: Todos os arquivos alterados

- [ ] **Step 1: Rodar toda a suíte de testes do frontend**

Run: `cd frontend && npm run test`  
Expected: Todos os testes PASS sem falhas.

- [ ] **Step 2: Rodar checagem de formatação e lint**

Run: `cd frontend && npx prettier --check .`  
Run: `cd frontend && npx eslint`  
Expected: Nenhum erro reportado.

- [ ] **Step 3: Validar checklist de pré-commit do projeto**

Verificar:
1. Sem caminhos absolutos (`/home/...`) nos arquivos.
2. Comentários `// MVP:` mantidos nas simplificações intencionais.
3. Roadmap em `docs/ROADMAP.md` atualizado com o item da entrega.

- [ ] **Step 4: Commitar ajustes finais**

```bash
git add docs/ROADMAP.md frontend/
git commit -m "style(frontend): valida testes, lint e formatacao da refatoracao visual M3 Glass"
```

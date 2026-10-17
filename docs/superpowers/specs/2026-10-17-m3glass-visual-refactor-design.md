# Design Spec: Refatoração Visual com Referência M3 Glass & Control iD

**Data:** 2026-10-17  
**Status:** Aprovado  
**Escopo:** Frontend (Home, Header, Footer, Catálogo `/produtos`, Componentes Visuais Dinâmicos, Responsividade Multi-Dispositivo e Ativos de Hardware)

---

## 1. Contexto e Objetivo

O projeto consiste em um assistente virtual multimodal para controle de acesso e segurança física (produtos da fabricante Control iD, tais como leitores faciais iDFace, catracas iDBlock, relógios de ponto REP iDClass e fechaduras digitais), operado sob a marca institucional **Empresa Fictícia**.

O objetivo desta refatoração é elevar a qualidade e sofisticação visual do frontend do patamar de protótipo básico para um padrão de excelência industrial e arquitetural inspirado diretamente em **https://www.m3glass.com/**, trazendo os elementos dinâmicos, contrastes refinados, tipografia de impacto e acabamento tecnológico do site referência, ao mesmo tempo em que preserva 100% da integridade técnica da aplicação (APIs REST, Server-Sent Events, Widget de Chat global, carrinho de compras, áreas administrativas e regras de formatação do repositório).

---

## 2. Princípios de Design & Identidade Visual

### 2.1 Identidade da Marca
* **Marca:** **Empresa Fictícia** (*Sistemas Integrados de Controle de Acesso e Segurança*).
* **Catálogo:** Linha oficial e produtos reais da **Control iD**, utilizando as fotografias de alta resolução presentes em `docs/Manuais_fornecedor/ControlId/`.
* **Badge Acadêmico:** Menção discreta no rodapé (*Protótipo de TCC — Inteligência Artificial Multimodal & Protocolo MCP*).

### 2.2 Paleta de Cores e Contraste
* **Tons Profundos (Dark Theme Sections - Hero, Header, Marquee, Footer):**
  * `bg-slate-950` (`#0B0F17`) como tela de fundo principal de contraste.
  * `bg-slate-900/90` (`#0F172A`) para superfícies elevadas e cards escuros com bordas sutis `border-slate-800`.
* **Tons Claros (Light Theme Sections - Catálogo, Soluções, Detalhes Técnicos):**
  * `bg-slate-50` (`#F8FAFC`) e `bg-white` para clareza em dados tabulares, especificações técnicas e fichas de produtos.
* **Acentos Tecnológicos:**
  * Azul Elétrico (`#2563EB` / `#3B82F6`) e Ciano Segurança (`#0EA5E9`) em gradientes discretos para CTAs, indicadores de foco e estados ativos.
  * Aço Inox Metálico (`#94A3B8` / `#CBD5E1`) refletindo a construção dos bloqueios físicos e catracas Control iD.

### 2.3 Tipografia e Acabamento
* Fonte: Geist Sans com variações de peso (300 a 800).
* Títulos principais com tracking condensado (`tracking-tight`) e subtítulos técnicos em caixa alta espaçada (`uppercase tracking-widest text-xs font-semibold text-blue-400`).
* Acabamento em *glassmorphism* suave (`backdrop-blur-md` com bordas translúcidas de 1px).

---

## 3. Arquitetura de Componentes & Efeitos Visuais Dinâmicos

A estrutura do frontend será organizada com componentes dedicados e reutilizáveis:

```
frontend/
├── app/
│   ├── layout.tsx                      # Header e Footer atualizados + ChatWidget
│   ├── page.tsx                        # Home Page reformulada estilo M3 Glass
│   ├── produtos/
│   │   └── page.tsx                    # Catálogo técnico com filtros e visual galeria
├── components/
│   ├── layout/
│   │   ├── Header.tsx                  # Navbar sticky translúcida com CTA dinâmico
│   │   ├── Footer.tsx                  # Footer em 4 colunas industriais estilo M3 Glass
│   ├── home/
│   │   ├── HeroSlider.tsx              # Slider com transição suave e card flutuante de métricas
│   │   ├── TechMarquee.tsx             # Infinite scrolling ticker com tecnologias
│   │   ├── CapabilitiesGrid.tsx        # Grade de 4 domínios com hover de elevação e borda luminosa
│   │   ├── HardwareReveal.tsx          # Efeito "Hover-Reveal" de hardware estilo M3 Glass (01 a 05)
│   │   ├── ProcessSteps.tsx            # Fluxo "Como Trabalhamos" 01-04 com linha de conexão
│   │   ├── MetricCounters.tsx          # Contadores numéricos dinâmicos com IntersectionObserver
│   │   └── FeaturedHardware.tsx        # Carrossel de hardware em destaque com fotos da Control iD
│   ├── products/
│   │   ├── ProductCard.tsx             # Card de produto moderno com tags e botões touch
│   │   └── ImageZoomModal.tsx          # Modal de visualização ampliada responsiva
│   └── ui/
│       └── Badge.tsx                   # Badges de tecnologia e status de estoque
├── public/
│   └── images/
│       └── products/                   # Fotos reais da Control iD copiadas dos manuais
└── lib/
    └── utils/
        └── resolveImageUrl.ts          # Resolução priorizada para fotos locais da Control iD
```

### 3.1 Detalhamento dos Componentes Dinâmicos da Home

#### A. HeroSlider (`components/home/HeroSlider.tsx`)
* **Dinâmica:** Slider interativo com 3 slides principais apresentando os pilares da Control iD:
  1. *Reconhecimento Facial 3D*: "Segurança Sem Contato e Validação em 0.2s" (iDFace / iDFace Max).
  2. *Bloqueios Físicos e Catracas*: "Engenharia de Alta Durabilidade em Aço Inox" (iDBlock / Torniquetes).
  3. *Gestão de Ponto em Nuvem*: "Conformidade Total com a Portaria 671 do MTE" (REP iDClass / RHiD).
* **Card Flutuante Lateral (`slider-element` M3 Glass):** Card translúcido com estatísticas chave que mudam dinamicamente conforme o slide ativo (tempo de leitura facial, capacidade de usuários, conformidade legal).
* **Controles:** Navegação por setas laterais, marcadores de slide e pausa automática ao posicionar o cursor.

#### B. TechMarquee (`components/home/TechMarquee.tsx`)
* **Dinâmica:** Faixa contínua com animação CSS suave (`@keyframes marquee`) sem sobrecarga de CPU, destacando termos chave: *Reconhecimento Facial 3D • Catracas de Inox • Portaria 671 • Leitores Veiculares UHF • Biometria Digital • Fechaduras Corporativas • Protocolo MCP B2B • Assistente IA Multimodal*.

#### C. HardwareReveal (`components/home/HardwareReveal.tsx`)
* **Dinâmica (Efeito M3 Glass `feature-item-list`):**
  * *Painel Esquerdo (Display de Hardware):* Fotografia ampla do equipamento em alta resolução com transição de fade suave e especificações essenciais.
  * *Painel Direito (Lista 01 a 05):*
    - `01. Terminal de Reconhecimento Facial iDFace`
    - `02. Catraca de Pedestal em Inox iDBlock`
    - `03. Relógio de Ponto Eletrônico REP iDClass`
    - `04. Leitor de Proximidade e Biometria iDAccess Pro`
    - `05. Fechadura Digital Corporativa iDLock`
  * No desktop, o display da esquerda muda instantaneamente ao passar o mouse sobre cada item. No smartphone e tablet, a seleção ocorre por toque direto no item numérico.

#### D. MetricCounters (`components/home/MetricCounters.tsx`)
* **Dinâmica:** Contadores numéricos que disparam uma animação suave de contagem progressiva via `IntersectionObserver` assim que a seção entra no campo de visão:
  * **`99.9%`** de Precisão em Reconhecimento Facial
  * **`0.2s`** Tempo Médio de Leitura Biométrica
  * **`100%`** Homologado pela Portaria 671 MTE
  * **`24/7`** Atendimento Inteligente com IA e MCP

#### E. ProcessSteps (`components/home/ProcessSteps.tsx`)
* **Dinâmica:** Grade dos 4 passos sequenciais do fluxo de atendimento inteligente (*01. Diagnóstico com Chat IA -> 02. Especificação & Cotação MCP -> 03. Fornecimento & Implantação -> 04. Suporte Especializado RAG*).

---

## 4. Estratégia de Responsividade Multi-Dispositivo

O layout e os efeitos visuais foram planejados especificamente para atender com perfeição aos três cenários exigidos:

### 4.1 Computador / Desktop (`>= 1024px` e `>= 1280px` - `lg` / `xl`) — Cenário Principal
* Header completo com links horizontais, busca, botão destacado de chat e menu admin.
* Hero com disposição lado a lado panorâmica (título e CTAs à esquerda, card de métricas flutuante à direita).
* HardwareReveal em divisão 50/50 com fotos grandes de alta resolução.
* Grids de 4 colunas em Capacidades e Processo.

### 4.2 Smartphone (`<= 640px` - `xs` / `sm`) — Cenário Secundário
* Header compacto com logo responsivo, botão de chat direto e menu lateral drawer completo.
* Hero verticalizado com títulos balanceados (`text-2xl` a `text-3xl`) e botões de ação em largura total (toque fácil para polegares).
* **HardwareReveal adaptado para toque:** Cada item se comporta como um acordeão ou abas tocáveis com feedback tátil e visual, sem dependência do evento de hover do mouse.
* Grids de 1 coluna com espaçamento entre cartões suficiente para evitar toques incorretos.
* Widget de chat flutuante com área de toque mínima de `48x48px` no canto inferior direito.

### 4.3 Tablet de 7 polegadas (`600px` a `800px` - `sm` a `md`) — Cenário Terciário
* Grids adaptados para 2 colunas (`sm:grid-cols-2`), mantendo legibilidade ideal sem compressão de texto.
* Hero com card de métricas proporcional abaixo da chamada principal.
* Carrossel de produtos exibindo 2 cartões simultâneos com setas de paginação touch visíveis.
* Área de busca e filtros do catálogo adaptados para largura intermediária.

---

## 5. Catálogo de Produtos (`/produtos`) & Gestão de Imagens

### 5.1 Catálogo Técnico de Equipamentos
* Header escuro com visual de galeria técnica M3 Glass, campo de busca com debounce de 300ms e atalhos de categoria em badges estilo pílula com rolagem horizontal touch.
* Lista de produtos integrada à API `GET /api/produtos`, com paginação no servidor e agrupamento inteligente por categoria.
* Suporte nativo ao modal de zoom (`ImageZoomModal`), permitindo inspecionar detalhes dos equipamentos.

### 5.2 Extração e Ingestão de Fotos Oficiais (`docs/Manuais_fornecedor/ControlId`)
As seguintes imagens de alta resolução serão copiadas para `frontend/public/images/products/`:
* `idface-frontal.jpg` (Terminal facial iDFace frontal)
* `idface-perspectiva.jpg` (Terminal facial iDFace em perspectiva)
* `idblock-inox.jpg` (Catraca iDBlock pedestal em inox)
* `idblock-preto.jpg` (Catraca iDBlock acabamento preto)
* `idblock-pcd.jpg` (Catraca iDBlock com acesso PCD)
* `idaccess-pro.jpg` (Controlador de acesso iDAccess Pro)
* `rep-idclass.jpg` (Relógio de ponto eletrônico REP iDClass)
* `idfit.jpg` / `idflex.jpg` / `idtouch.jpg` (Controladores e leitores biométricos)

O utilitário `lib/utils/resolveImageUrl.ts` será atualizado para mapear os nomes e categorias desses produtos para os arquivos locais de alta definição sempre que disponíveis, mantendo o fallback transparente para as imagens do backend.

---

## 6. Preservação de Contratos & Conformidade de Código

### 6.1 Contratos Preservados
* `ChatWidget` e `useChatStore`: Funcionamento idêntico em todas as rotas (modal central, streaming SSE, cards ricos).
* APIs REST: Nenhuma alteração nos contratos de `/api/produtos`, `/api/pedidos`, `/api/auth` e rotas de agendamento.
* Rotas Administrativas (`/admin/*`): Layout intacto com ocultação automática do Footer para evitar barras de rolagem redundantes.

### 6.2 Regras de Formatação e Qualidade
* **Prettier:** `printWidth: 100`, `singleQuote: false`, `semi: true`, `trailingComma: "all"`.
* **ESLint:** Execução sem avisos ou erros (`npx eslint`).
* **Testes:** Suíte do Vitest (`npm run test`) atualizada e validada, adaptando seletores que tenham sido enriquecidos para garantir 100% de aprovação.

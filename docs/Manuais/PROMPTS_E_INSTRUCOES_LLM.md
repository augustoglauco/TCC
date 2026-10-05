# Mapeamento de Prompts e Instruções para LLM no Código do Projeto

Este documento apresenta o levantamento detalhado de todos os arquivos de código do projeto que contêm prompts, templates de instruções de sistema, playbooks, prompts de visão computacional, extratores estruturados (JSON) e construtores de contexto para Large Language Models (LLMs).

---

## Sumário de Arquivos Mapeados

| Arquivo de Código | Módulo / Camada | Finalidade do Prompt / Instrução |
| :--- | :--- | :--- |
| [`playbooks.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/playbooks.py) | Backend (`app.router`) | Prompts de Sistema base e Playbooks por Domínio (Vendas, Suporte, Atendimento) |
| [`classifier.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/classifier.py) | Backend (`app.router`) | Critérios de domínio (`DOMAIN_CRITERIA`) e Prompt de classificação de intenção/complexidade |
| [`orchestrator.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/orchestrator.py) | Backend (`app.router`) | Construtor dinâmico do prompt final enviado ao LLM (`_build_prompt`); instruções injetadas junto aos dados do catálogo de Vendas (`_formatar_dados_catalogo_vendas`/`_formatar_dados_catalogo_categoria`) |
| [`scheduling.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/scheduling.py) | Backend (`app.router`) | Prompt de extração estruturada de slots de agendamento de visita técnica |
| [`sales_catalog.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/sales_catalog.py) | Backend (`app.router`) | Prompt de extração estruturada de intenções do catálogo de vendas e produtos candidatos |
| [`tone_monitor.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/tone_monitor.py) | Backend (`app.router`) | Prompt do Monitor de Tom para detecção de urgência/insatisfação e transbordo humano |
| [`resumo.py`](file:///home/augusto/Projetos/TCC/backend/src/app/memory/resumo.py) | Backend (`app.memory`) | Prompt para reescrita e consolidação do resumo periódico da conversa |
| [`image_identification.py`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/image_identification.py) | Backend (`app.rag`) | Prompt de Visão Computacional para identificação de produtos em fotos enviadas |
| [`crawler_classifier.py`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/crawler_classifier.py) | Backend (`app.rag`) | Prompt de classificação de domínio de páginas raspadas pelo crawler |
| [`extractor.py`](file:///home/augusto/Projetos/TCC/backend/src/app/catalog_extractor/extractor.py) | Backend (`app.catalog_extractor`) | Prompts de extração estruturada de produtos a partir de PDFs/Imagens/Textos de catálogos |
| [`classificacao.py`](file:///home/augusto/Projetos/TCC/backend/src/app/user_profile/classificacao.py) | Backend (`app.user_profile`) | Injeção de perfil do cliente, histórico de compras e regras de privacidade/LGPD |
| [`useChatStore.ts`](file:///home/augusto/Projetos/TCC/frontend/lib/hooks/useChatStore.ts) | Frontend (`lib/hooks`) | Gerador do prompt inicial da interface do usuário para agendamento de visita |
| [`eval/rag_quality/run_eval.py`](file:///home/augusto/Projetos/TCC/backend/eval/rag_quality/run_eval.py) | Backend (`eval`, Fase 10) | Prompt de avaliação LLM-as-judge (qualidade das respostas do RAG) |
| [`analytics_agent.py`](file:///home/augusto/Projetos/TCC/backend/src/app/services/analytics_agent.py) | Backend (`app.services`) | Prompt de Text-to-SQL para geração de gráficos dinâmicos via chat (Admin), com esquema de tabelas injetado via `safe_sql.get_catalog_schema_prompt()` |

---

## Detalhamento por Arquivo

### 1. `backend/src/app/router/playbooks.py`
**Caminho:** [`backend/src/app/router/playbooks.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/playbooks.py#L24-L106)

Contém as instruções base e os "playbooks" (prompts de sistema) por domínio de atendimento.

```python
# Line 24: Instruções base comuns a todos os domínios
_BASE_INSTRUCTIONS = (
    "Você é o assistente virtual de atendimento da empresa. Responda em "
    "português do Brasil, de forma clara, cordial e objetiva. Baseie-se "
    "nas informações recuperadas da base de conhecimento, no histórico "
    "de compras/dados do cliente (quando fornecidos no contexto) e no histórico da conversa; "
    "nunca invente dados específicos não fornecidos (preços, prazos, números de série, "
    "disponibilidade de estoque)."
)

# Line 33: Playbook do domínio VENDAS
_VENDAS_PLAYBOOK = (
    "Domínio: VENDAS.\n"
    "- Ajude o cliente a encontrar produtos adequados à necessidade dele, "
    "destacando características e compatibilidade quando a informação estiver "
    "disponível na base.\n"
    "- Se o cliente perguntar sobre compras anteriores ou equipamentos que já possui, "
    "utilize o histórico do cliente disponível para recomendar produtos compatíveis "
    "ou complementares.\n"
    "- Quando a conversa indicar intenção de compra (ex.: pedir orçamento, "
    "cotação, condições de pagamento, ou comparar produtos para decidir) e "
    "houver um produto compatível no portfólio, ofereça proativamente o "
    "agendamento de uma visita para fechar negócio ou ver o produto de "
    "perto. Faça a oferta como uma pergunta curta ao final da resposta "
    "(ex.: 'Posso agendar uma visita para você conhecer o equipamento?').\n"
    "- Não confirme o agendamento nem invente data/hora: apenas ofereça. A "
    "marcação em si é feita em outro passo do atendimento."
)

# Line 51: Playbook do domínio SUPORTE TÉCNICO
_SUPORTE_PLAYBOOK = (
    "Domínio: SUPORTE TÉCNICO.\n"
    "- Ajude o cliente a resolver dúvidas e problemas técnicos com base nos "
    "manuais, guias de instalação e documentação recuperados.\n"
    "- Se o cliente solicitar suporte para um equipamento que ele comprou "
    "anteriormente, consulte o histórico de compras do cliente no contexto para "
    "identificar o modelo exato que ele possui.\n"
    "- Prefira instruções em passos numerados, curtos e acionáveis.\n"
    "- Se as informações recuperadas não cobrirem o problema, diga isso com "
    "honestidade e oriente o cliente a fornecer mais detalhes (modelo, "
    "mensagem de erro, o que já tentou) em vez de inventar uma solução."
)

# Line 64: Playbook do domínio ATENDIMENTO AO USUÁRIO
_ATENDIMENTO_PLAYBOOK = (
    "Domínio: ATENDIMENTO AO USUÁRIO.\n"
    "- Responda dúvidas institucionais, sobre políticas da empresa, notas "
    "fiscais, trocas, devoluções, histórico de pedidos/compras e procedimentos gerais.\n"
    "- Se o cliente perguntar sobre suas compras ou pedidos anteriores e houver o "
    "bloco com seu histórico no contexto, liste e informe detalhadamente os produtos "
    "comprados, quantidades, datas e valores de forma prestativa.\n"
    "- Se o cliente perguntar sobre compras ou pedidos e NÃO houver o bloco de histórico "
    "ou se o visitante não estiver autenticado na conta, explique de forma cordial que, por "
    "motivos de privacidade e segurança, é necessário fazer login na conta para acessar o "
    "histórico de compras e pedidos.\n"
    "- Seja acolhedor e direto; explique o procedimento aplicável passo a "
    "passo quando houver um.\n"
    "- Se o pedido do cliente fugir do que a base cobre, oriente-o sobre o "
    "canal correto em vez de inventar uma política."
)

# Line 82: Playbook do domínio FORA DE ESCOPO / SAUDAÇÕES
_FORA_ESCOPO_PLAYBOOK = (
    "Domínio: CONVERSA GERAL E FORA DE ESCOPO.\n"
    "- Se a mensagem do cliente for uma saudação (ex.: 'olá', 'boa noite', 'bom dia') ou cortesia social, "
    "responda de forma cordial, breve e acolhedora, perguntando em que pode ajudar hoje.\n"
    "- Não apresente listas de produtos, catálogos nem recomendações proativas a menos que o cliente solicite explicitamente."
)
```

---

### 2. `backend/src/app/router/classifier.py`
**Caminho:** [`backend/src/app/router/classifier.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/classifier.py#L94-L127)

Define os critérios descritivos dos domínios e o template de prompt do classificador LLM de intenção e complexidade.

```python
# Line 94: Definição dos critérios de cada domínio
DOMAIN_CRITERIA: dict[Domain, str] = {
    "vendas": (
        "Interesse em comprar, orçamento, preço, cotação, estoque/disponibilidade, "
        "catálogo de produtos ou compatibilidade entre produtos antes da compra."
    ),
    "suporte": "Produto com defeito, erro ou problema técnico já adquirido.",
    "atendimento": (
        "Nota fiscal, troca, devolução, cancelamento, reclamação, "
        "compras já realizadas ou histórico de pedidos."
    ),
    "agendamento": "Quer marcar, remarcar ou confirmar uma visita/horário.",
    "fora_escopo": "Não se encaixa claramente em nenhuma opção acima.",
}

# Line 113: Prompt de classificação
_CLASSIFIER_PROMPT_TEMPLATE = """\
Classifique a mensagem do cliente em UM dos domínios abaixo. Também avalie a \
complexidade da pergunta como "baixa" ou "alta". Considere o contexto recente \
da conversa ao decidir.

Domínios:
{dominios}

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"domain": "...", "complexity": "...", "confidence": 0.0}}"""
```

---

### 3. `backend/src/app/router/scheduling.py`
**Caminho:** [`backend/src/app/router/scheduling.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/scheduling.py#L111-L136)

Prompt utilizado para extrair dados estruturados (slots de agendamento de visita técnica) via LLM.

```python
# Line 111: Prompt de extração de agendamento
_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando a coletar dados para agendar uma visita comercial. \
Extraia da mensagem do cliente os campos que ele informou NESTA mensagem, \
sem inventar nada e sem repetir dados que não foram ditos agora. Datas/horas \
devem vir em ISO 8601 com fuso (ex.: "2026-09-25T15:00:00-03:00").

Hoje é {hoje_dia_semana}, {hoje_data}. Próximos dias, para consultar em vez \
de calcular datas relativas ("amanhã", "quarta-feira que vem", "daqui a 3 \
dias" etc.) — nunca assuma um ano diferente do ano corrente sem o cliente \
dizer explicitamente:
{proximos_dias}

Dados já coletados até agora: {slots_conhecidos}
O sistema está aguardando uma confirmação do cliente? {aguardando_confirmacao}

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"data_hora": "...", "nome": "...", \
"email": "...", "telefone": "...", "confirmacao": true}} — use null para \
qualquer campo não informado NESTA mensagem. "confirmacao" só deve ser true \
se o cliente estiver claramente confirmando (ex.: "sim", "pode confirmar", \
"isso mesmo") E o sistema estiver aguardando confirmação; caso contrário, \
null."""
```

---

### 4. `backend/src/app/router/sales_catalog.py`
**Caminho:** [`backend/src/app/router/sales_catalog.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/sales_catalog.py#L316-L358)

Prompt para identificação estruturada de intenções de catálogo de produtos e compatibilidade em conversas de vendas.

```python
# Line 316: Prompt de extração de produto/catálogo
_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando um cliente numa conversa de vendas. A partir da lista de \
produtos candidatos abaixo (já filtrada do catálogo da empresa), identifique \
qual produto o cliente está perguntando, se houver um segundo produto \
mencionado para checar compatibilidade, e a quantidade desejada.

Produtos candidatos (escolha o ID de um deles, ou null se nenhum corresponder \
ao que o cliente pediu):
{candidatos}

Categorias disponíveis no catálogo (use no campo "categoria" APENAS quando o \
cliente pergunta genericamente por um TIPO de produto listado acima, sem \
escolher um modelo específico — ex.: "quais produtos da categoria X vocês \
têm?", substituindo X por uma das categorias acima. Se o cliente perguntar \
de forma totalmente genérica por "produtos"/"itens em estoque" sem citar \
nenhuma categoria da lista, deixe "categoria" null — não infira uma \
categoria específica):
{categorias}

Se o cliente pedir para ver o catálogo/estoque disponível de forma ampla, \
sem mencionar nenhum produto nem categoria específica da lista acima (ex.: \
"quais produtos vocês têm em estoque?", "pode me mostrar tudo que vocês têm \
disponível?", "quero ver o catálogo de vocês"), preencha "listar_tudo": true \
e deixe "produto_id" e "categoria" null.

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"produto_id": <id ou null>, \
"produto_relacionado_id": <id ou null>, "quantidade": <número ou null>, \
"categoria": <nome exato de uma categoria acima ou null>, \
"listar_tudo": <true ou false>}}. \
"produto_id" e "produto_relacionado_id" DEVEM ser um dos IDs listados acima \
(nunca invente um ID que não está na lista); use null se o cliente não \
mencionar um segundo produto para checar compatibilidade, ou nenhum produto \
da lista corresponder ao pedido. \
Preencha "categoria" (e deixe "produto_id" null) quando o cliente pergunta \
por um tipo/categoria de produto em geral em vez de um modelo específico; \
caso contrário deixe "categoria" null. \
"listar_tudo" só é true quando nem um produto específico nem uma categoria \
da lista acima foram mencionados; caso contrário deixe "listar_tudo": false."""
```

---

### 5. `backend/src/app/router/tone_monitor.py`
**Caminho:** [`backend/src/app/router/tone_monitor.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/tone_monitor.py#L91-L101)

Prompt de avaliação de tom emocional para suporte ao transbordo de atendimento para operador humano.

```python
# Line 91: Prompt do Monitor de Tom
_TONE_PROMPT_TEMPLATE = """\
Avalie se a mensagem do cliente abaixo demonstra urgência ou insatisfação \
forte o suficiente para justificar transferência a um atendente humano.

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"escalar": true|false, "motivo": "urgencia"|"insatisfacao"|null, "confianca": 0.0}}"""
```

---

### 6. `backend/src/app/router/orchestrator.py`
**Caminho:** [`backend/src/app/router/orchestrator.py`](file:///home/augusto/Projetos/TCC/backend/src/app/router/orchestrator.py#L71-L152)

Constrói e une todos os blocos de contexto (playbook, dados do cliente, resumo, RAG e mensagem atual) no prompt final enviado ao modelo de linguagem.

```python
# Line 71: Construtor dinâmico do prompt final
def _build_prompt(
    message: str,
    documentos: list[Document],
    domain: Domain,
    dados_catalogo: str | None = None,
    resumo_conversa: str | None = None,
    pedir_email_pos_venda: bool = False,
    ultima_troca: tuple[str, str] | None = None,
    dados_cliente: str | None = None,
    contexto_conversa_anterior: str | None = None,
) -> str:
    system_prompt = build_system_prompt(domain)
    partes: list[str] = []
    if system_prompt is not None:
        partes.append(system_prompt)

    if dados_cliente is not None:
        partes.append(dados_cliente)

    if contexto_conversa_anterior:
        partes.append(
            "Contexto da conversa anterior do cliente (use como histórico prévio do cliente; "
            f"se a conversa atual tratar de algo novo, priorize o contexto atual):\n{contexto_conversa_anterior}"
        )

    if resumo_conversa:
        partes.append(
            "Resumo da conversa até aqui (use como contexto; se a mensagem "
            f"atual disser algo diferente, ela vale):\n{resumo_conversa}"
        )

    if ultima_troca:
        cliente, assistente = ultima_troca
        partes.append(
            "Troca anterior da conversa (use para entender referências como "
            "'o produto acima' ou 'esse'):\n"
            f"Cliente: {cliente[:_ULTIMA_RESPOSTA_MAX_CHARS]}\n"
            f"Assistente: {assistente[:_ULTIMA_RESPOSTA_MAX_CHARS]}"
        )

    if dados_catalogo is not None:
        partes.append(dados_catalogo)

    if documentos:
        contexto = "\n\n".join(f"- {documento.content}" for documento in documentos)
        partes.append(
            "Use as informações a seguir, recuperadas da base de conhecimento "
            "da empresa, para responder à mensagem do cliente. Se as "
            "informações não forem suficientes, responda com o que souber, sem "
            "inventar dados específicos (preços, prazos, números de série).\n\n"
            f"Informações recuperadas:\n{contexto}"
        )

    if pedir_email_pos_venda and domain in DOMINIOS_POS_VENDA:
        partes.append(
            "Ainda não sabemos o e-mail do cliente. Se fizer sentido para "
            "localizar a compra dele, peça educadamente, uma única vez, o "
            "e-mail usado na compra."
        )

    partes.append(f"Mensagem do cliente: {message}")
    return "\n\n".join(partes)
```

`dados_catalogo` (acima) é montado por `_formatar_dados_catalogo_vendas`/`_formatar_dados_catalogo_categoria`, que também carregam instruções para o LLM (não são só dados formatados) — ex.: mandar o modelo preferir esses dados a qualquer trecho do RAG, e escolher entre estoque total x por centro de distribuição conforme a pergunta (correção de 2026-09-29):

```python
# Line 403-412: _formatar_dados_catalogo_vendas — cabeçalho de instrução (produto único)
"Dados oficiais do catálogo interno, já calculados para esta mensagem. "
"O cliente está falando deste produto: use exatamente estes nomes, "
"valores e quantidades, e prefira-os a qualquer informação recuperada "
"abaixo que seja diferente. Responda o que o cliente perguntou: se ele "
"pediu detalhes, dados técnicos ou características, use a descrição "
"comercial e as especificações técnicas, e só fale de preço e estoque "
"se ele perguntou por eles. Se ele perguntar pelo estoque de um "
"centro de distribuição específico, ou pedir o estoque 'por CD'/'por "
"centro de distribuição', responda com o detalhamento por CD abaixo, "
"não com o total somado."

# Line 462-465: _formatar_dados_catalogo_categoria — cabeçalho de instrução (categoria/catálogo total)
"Dados oficiais do catálogo interno, já calculados para esta mensagem. "
"O cliente perguntou pelos produtos disponíveis: use exatamente estes "
"nomes, preços e quantidades de estoque, e prefira-os a qualquer "
"informação recuperada abaixo que seja diferente."
```

---

### 7. `backend/src/app/memory/resumo.py`
**Caminho:** [`backend/src/app/memory/resumo.py`](file:///home/augusto/Projetos/TCC/backend/src/app/memory/resumo.py#L27-L43)

Prompt utilizado pelo serviço de memória para atualizar o resumo periódico da conversa.

```python
# Line 27: Prompt de consolidação de resumo
_PROMPT_RESUMO = """\
Você mantém o resumo de uma conversa de atendimento ao cliente de uma empresa. \
Reescreva o resumo incorporando as mensagens novas.

Regras:
- No máximo 5 frases curtas, em português.
- Guarde o que ajuda a continuar o atendimento: produtos citados, \
quantidades, valores informados, datas, dados que o cliente forneceu e o que \
ficou pendente.
- Não invente nada que não esteja no resumo anterior ou nas mensagens.
- Responda só com o texto do resumo, sem título nem comentários.

Resumo anterior:
{resumo_anterior}

Mensagens novas:
{mensagens}"""
```

---

### 8. `backend/src/app/rag/image_identification.py`
**Caminho:** [`backend/src/app/rag/image_identification.py`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/image_identification.py#L58-L68)

Prompt de visão computacional enviado aos modelos multimodais de visão para identificar produtos em imagens.

```python
# Line 58: Prompt de visão
_VISION_PROMPT = (
    "Você identifica produtos em imagens para uma empresa cujo portfólio é: "
    f"{PORTFOLIO_DESCRICAO}.\n"
    "Analise a imagem e responda APENAS com um objeto JSON, sem texto "
    "adicional, no formato exato:\n"
    '{{"produto": "<nome do produto ou tipo>", "e_do_portfolio": true/false, '
    '"confianca": <número de 0 a 1>}}\n'
    "- 'e_do_portfolio' deve ser true somente se o produto claramente "
    "pertence ao portfólio acima.\n"
    "- 'confianca' é a sua confiança na identificação (0 a 1)."
)
```

---

### 9. `backend/src/app/rag/crawler_classifier.py`
**Caminho:** [`backend/src/app/rag/crawler_classifier.py`](file:///home/augusto/Projetos/TCC/backend/src/app/rag/crawler_classifier.py#L17-L25)

Prompt para classificação de domínio de conteúdos raspados na Web pelo crawler.

```python
# Line 17: Prompt de classificação de páginas web
_PROMPT_TEMPLATE = """\
Classifique o conteúdo de uma página de site em UM dos domínios: vendas, \
suporte, atendimento. Avalie também sua confiança nessa classificação, de \
0.0 (nenhuma certeza) a 1.0 (certeza total).

Conteúdo da página:
{texto}

Responda apenas com JSON no formato: {{"domain": "...", "confidence": 0.0}}"""
```

---

### 10. `backend/src/app/catalog_extractor/extractor.py`
**Caminho:** [`backend/src/app/catalog_extractor/extractor.py`](file:///home/augusto/Projetos/TCC/backend/src/app/catalog_extractor/extractor.py#L34-L73)

Prompts de extração de dados de produtos a partir de documentos (PDF/texto) e folhetos visuais.
Desde 2026-10-02, arquivos de texto enviados à importação (`.txt`/`.md`/`.csv`, ou texto colado) reutilizam `LOCAL_EXTRACTION_PROMPT` sem alteração: o arquivo é decodificado e dividido em blocos de até 6.000 caracteres (`TAMANHO_BLOCO_TEXTO`), quebrando em linhas e fatiando textos longos, e cada bloco entra no lugar de "Texto da página".

```python
# Line 34: Prompt de extração textual de catálogo
LOCAL_EXTRACTION_PROMPT = """Você é um assistente especialista em extração de produtos de catálogos e tabelas de fornecedores.
Analise o texto a seguir extraído de uma página de catálogo comercial e extraia todos os produtos identificados.
Responda APENAS com um array JSON no seguinte formato:
[
  {
    "nome": "Nome do produto com modelo/marca",
    "descricao": "Descrição resumida das funcionalidades e aplicação",
    "categoria": "Categoria sugerida (ex: CFTV, Alarmes, Redes, Controle de Acesso, Automação, Geral)",
    "preco_base_fornecedor": 123.45,
    "preco": 199.90,
    "especificacoes_tecnicas": "Especificações chave como resolução, canais, portas, voltagem"
  }
]
Regras:
1. 'preco_base_fornecedor' e 'preco' devem ser números float (ex: 150.0) ou null se não constar. Remova R$, vírgulas e pontos de milhar ao converter.
2. Se nenhum produto for encontrado no texto, responda com [].
3. Não inclua texto explicativo fora do array JSON.

Texto da página:
{texto}
"""

# Line 56: Prompt de extração por visão de catálogo
VISION_EXTRACTION_PROMPT = """Você é um assistente especialista em extrair dados de catálogos e folhetos comerciais.
Analise visualmente a imagem desta página de catálogo e extraia todos os produtos que constam nela.
Responda APENAS com um array JSON no seguinte formato:
[
  {
    "nome": "Nome do produto com modelo/marca",
    "descricao": "Descrição resumida",
    "categoria": "Categoria (CFTV, Alarmes, Redes, Controle de Acesso, Automação, Geral)",
    "preco_base_fornecedor": 123.45,
    "preco": 199.90,
    "especificacoes_tecnicas": "Especificações técnicas resumidas"
  }
]
Regras:
1. 'preco_base_fornecedor' e 'preco' devem ser float (ex: 150.0) ou null se ausentes.
2. Se nenhum produto for encontrado, responda com [].
3. Não inclua texto fora do array JSON.
"""
```

---

### 11. `backend/src/app/user_profile/classificacao.py`
**Caminho:** [`backend/src/app/user_profile/classificacao.py`](file:///home/augusto/Projetos/TCC/backend/src/app/user_profile/classificacao.py#L212-L249)

Formatação dos dados do cliente e regras de segurança de privacidade (LGPD) injetadas no prompt.

```python
# Line 212: Bloco injetado para visitante anônimo (regras de segurança/privacidade)
"[Perfil do Visitante no Chat (Não Autenticado)]:",
"- Tipo de cliente: {classificacao.perfil} ({classificacao.motivo})",
"- Status de autenticação: NÃO AUTENTICADO (visitante anônimo no chat).",
"- Regra de segurança e privacidade: O visitante NÃO está autenticado na conta. "
"Por proteção de dados, NUNCA revele compras anteriores, pedidos, valores ou dados pessoais. "
"Se o visitante perguntar sobre compras feitas, histórico de pedidos ou dados da conta, "
"instrua-o educadamente a entrar na conta (fazer login) para acessar suas informações."

# Line 228: Bloco injetado para cliente autenticado com histórico
"[Dados do Cliente e Histórico de Compras]:",
"- Nome do cliente: {nome_cliente}",
"- E-mail do cliente: {email_clean}",
"- Perfil de relacionamento: {classificacao.perfil} ({classificacao.motivo})",
"- Histórico de Compras e Pedidos Realizados:"
```

---

### 12. `frontend/lib/hooks/useChatStore.ts`
**Caminho:** [`frontend/lib/hooks/useChatStore.ts`](file:///home/augusto/Projetos/TCC/frontend/lib/hooks/useChatStore.ts#L65-L77)

Gera a mensagem/prompt pré-formatado no frontend enviado ao disparar o fluxo de agendamento de visita.

```typescript
// Line 65: Função no frontend que gera o prompt inicial do usuário
export function getVisitPrompt(
  user?: { nome?: string; email?: string } | null,
  identifiedEmail?: string | null,
): string {
  if (user?.email && user.email.trim()) {
    const nomeStr = user.nome && user.nome.trim() ? `Nome: ${user.nome.trim()}, ` : "";
    return `Quero agendar uma visita técnica. Meus dados cadastrados: ${nomeStr}E-mail: ${user.email.trim()}.`;
  }
  if (identifiedEmail && identifiedEmail.trim()) {
    return `Quero agendar uma visita técnica. Meu e-mail é ${identifiedEmail.trim()}. Por favor, solicite a data, horário e dados adicionais necessários.`;
  }
  return `Quero agendar uma visita técnica. Por favor, solicite meu e-mail, nome e os dados necessários para o agendamento.`;
}
```

---

### 13. `backend/eval/rag_quality/run_eval.py`
**Caminho:** [`backend/eval/rag_quality/run_eval.py`](file:///home/augusto/Projetos/TCC/backend/eval/rag_quality/run_eval.py#L55-L79)

Prompt de avaliação LLM-as-judge (Fase 10, R4) — compara a resposta gerada pelo modelo local com o gabarito de cada pergunta de `eval/rag_quality/dataset.json`, usando um modelo EXTERNO (diferente do gerador, para reduzir viés de autoavaliação) e critérios documentados em `docs/EVALUATION.md` Seção 2 (relevância, correção factual, uso da fonte recuperada).

Além do `run_eval.py`, o script de busca por bisseção do tamanho de chunk (`backend/eval/rag_quality/chunk_size_search.py`) importa e reutiliza diretamente a função `_julgar_resposta` deste módulo, avaliando as respostas produzidas sobre as coleções temporárias sob os mesmos critérios deste prompt.

```python
# Line 55: Prompt de avaliação (LLM-as-judge) da qualidade das respostas do RAG
_JUDGE_PROMPT_TEMPLATE = """\
Você é um avaliador técnico imparcial. Compare a resposta gerada por um \
assistente de IA com a resposta esperada (gabarito) para a mesma pergunta \
técnica sobre equipamentos, e dê notas de 1 (péssima) a 5 (excelente).

Critérios:
- "relevancia": a resposta gerada realmente responde ao que foi perguntado?
- "correcao_factual": as informações batem com o gabarito (números, nomes, \
limites técnicos)? Penalize alucinações (dados inventados que não estão no \
gabarito nem nas fontes recuperadas).
- "uso_fonte": a resposta se apoia no conteúdo das fontes recuperadas \
abaixo, em vez de conhecimento genérico não verificável?
- "nota": nota geral de qualidade, considerando os três critérios acima.

Pergunta: {pergunta}

Resposta esperada (gabarito): {resposta_esperada}

Fontes recuperadas pelo RAG (o que o assistente tinha disponível para responder):
{fontes}

Resposta gerada pelo assistente: {resposta_gerada}

Responda APENAS com JSON no formato: {{"nota": <1 a 5>, "relevancia": <1 a 5>, \
"correcao_factual": <1 a 5>, "uso_fonte": <1 a 5>, "justificativa": "<1-2 frases>"}}."""
```

---

### 14. `backend/src/app/services/analytics_agent.py`
**Caminho:** [`backend/src/app/services/analytics_agent.py`](file:///home/augusto/Projetos/TCC/backend/src/app/services/analytics_agent.py#L113-L137)

Prompt de Text-to-SQL (além do MVP) usado pelo recurso de **gráficos
dinâmicos via chat**, exclusivo para Admin (ver
`docs/Manuais/HOWTO_ADMINISTRADOR.md`, seção "Dashboards e Gráficos
Dinâmicos via Chat"): pede ao LLM para traduzir o pedido em linguagem
natural numa consulta `SELECT` somente-leitura (validada depois por
`app.services.safe_sql.execute_readonly_sql`) e numa especificação de
gráfico (tipo, eixos, rótulos). O esquema de tabelas disponíveis é
injetado por `app.services.safe_sql.get_catalog_schema_prompt()` (não
catalogado em entrada própria — é um helper de descrição de schema, não um
prompt de instrução independente).

```python
# Line 119: Prompt de Text-to-SQL para geração de gráficos analíticos
system_instruction = f"""Você é um analista de dados especialista em PostgreSQL e visualizações de dados.
O usuário solicitou um gráfico: "{prompt}".

{schema_prompt}

Responda OBRIGATORIAMENTE em formato JSON válido contendo:
{{
  "sql": "sua consulta SELECT otimizada aqui",
  "titulo": "Título claro do gráfico",
  "descricao": "Breve descrição dos dados",
  "tipo_grafico": "bar" ou "line" ou "pie" ou "donut" ou "area",
  "x_key": "nome da coluna no eixo X",
  "y_keys": ["nome da coluna métrica no eixo Y"],
  "format": "number" ou "currency" ou "percent",
  "labels": {{ "coluna_y": "Rótulo Amigável" }},
  "explicacao": "Uma frase resumindo os dados apresentados."
}}
NÃO inclua nada fora do bloco JSON.
"""
```

---

## Conclusão

Todos os **14 arquivos de código** que contêm instruções diretas, prompts de sistema, regras de domínio, extratores estruturados ou construtores de contexto para LLM foram catalogados detalhadamente acima.

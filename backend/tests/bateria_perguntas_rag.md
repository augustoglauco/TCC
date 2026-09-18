# 🎯 Bateria de Teste e Benchmark RAG — Equipamentos & Manuais Intelbras

Este documento contém uma bateria de **20 perguntas de teste** classificadas por nível de dificuldade (**Fácil, Média e Difícil**), elaboradas a partir do processamento e extração de texto via `pdfplumber` dos manuais e datasheets contidos em `/home/augusto/Projetos/TCC/docs/Manuais_fornecedor`.

---

## 📊 Visão Geral do Benchmark

| Categoria | Qtd | Foco Principal | Capacidade Avaliada no RAG |
| :--- | :---: | :--- | :--- |
| **🟢 Fácil** | 7 | Fatos Diretos e Parâmetros Numéricos | Recuperação precisa de 1 chunk isolado |
| **🟡 Média** | 7 | Comparativos, Tabelas e Regras de Negócio | Múltiplos chunks, síntese de dados e tabelas |
| **🔴 Difícil** | 6 | Arquitetura, Raciocínio Técnico e RAG Negativo | Resolução de projetos e recusa a alucinações |

---

## 🟢 Nível 1: Perguntas Fáceis (7 Perguntas)

### Q1. Quantidade de Contas SIP no Telefone V3001
* **Pergunta**: Quantas contas SIP o telefone IP Intelbras V3001 permite registrar?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Manual_V3001_01-26_site.pdf` (Pág. 5 e 19)
* **Resposta Esperada (Gabarito)**: O telefone IP V3001 permite registrar até **2 contas SIP** independentes.
* **O que avalia no RAG**: Extração direta de parâmetro numérico de hardware/software.

---

### Q2. Capacidade de Canais do Servidor iNVU 9164
* **Pergunta**: Qual é a capacidade máxima de canais de vídeo do servidor iNVU 9164 M2 IAX FT?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 1 e 2)
* **Resposta Esperada (Gabarito)**: Suporta até **64 canais** de vídeo.
* **O que avalia no RAG**: Extração exata do modelo e sua capacidade de entradas de vídeo.

---

### Q3. Alcance do Infravermelho da Câmera VIP 7550
* **Pergunta**: Qual é a distância máxima do iluminador infravermelho (IR Inteligente) da câmera VIP 7550 BD Z IA?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Datasheet 7550 BD Z IA FT - V018_0.pdf` (Pág. 2)
* **Resposta Esperada (Gabarito)**: O alcance máximo do IR Inteligente é de **50 metros**.
* **O que avalia no RAG**: Busca vetorial por especificação de iluminação e óptica.

---

### Q4. Propósito do Software IP Utility
* **Pergunta**: O que é o software IP Utility e para que ele serve?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Manual_IP_Utility_01-26_site_4.pdf` (Pág. 2)
* **Resposta Esperada (Gabarito)**: O IP Utility é um software utilitário secundário da Intelbras desenvolvido para localizar dispositivos de segurança eletrônica na rede local e auxiliar na configuração de padrões de imagem e rede.
* **O que avalia no RAG**: Recuperação do propósito geral do software.

---

### Q5. Limite de Canais InSearch no iNVU 9164
* **Pergunta**: Quantos canais de gravação InSearch simultâneos o iNVU 9164 M2 IAX suporta via servidor?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 4)
* **Resposta Esperada (Gabarito)**: Suporta busca utilizando InSearch em até **16 canais**.
* **O que avalia no RAG**: Recuperação de limites específicos de inteligência artificial.

---

### Q6. Resolução Máxima do iNVU 9164
* **Pergunta**: Qual é a resolução máxima de gravação suportada pelo iNVU 9164 M2 IAX FT?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 2 e 3)
* **Resposta Esperada (Gabarito)**: A resolução máxima é de **32 Megapixels (32 MP)**.
* **O que avalia no RAG**: Extração de atributo técnico de resolução de imagem.

---

### Q7. Quantidade de Áreas DMI 3.0 na VIP 7550
* **Pergunta**: Quantas áreas de Detecção de Movimento Inteligente (DMI 3.0) é possível configurar na VIP 7550 BD Z IA?
* **Dificuldade**: Fácil
* **Documento de Origem**: `Datasheet 7550 BD Z IA FT - V018_0.pdf` (Pág. 3)
* **Resposta Esperada (Gabarito)**: Podem ser configuradas até **4 áreas** com agendamento.
* **O que avalia no RAG**: Leitura correta de recursos de inteligência perimetral.

---

## 🟡 Nível 2: Perguntas Médias (7 Perguntas)

### Q8. Comparativo Intelbras Defense IA vs Defense IA Lite (Redundância)
* **Pergunta**: Qual é a diferença entre as versões Intelbras Defense IA Lite e Intelbras Defense IA referente à implantação e redundância?
* **Dificuldade**: Média
* **Documento de Origem**: `Comparativo de funções - Intelbras Defense IA & Lite - V1.pdf` (Pág. 3)
* **Resposta Esperada (Gabarito)**: O **Defense IA Lite** (versão gratuita) suporta apenas implantação em **Servidor Único** e não possui recurso de *Hot Standby* nem suporte a servidores em cascata/distribuído. Já o **Defense IA** (versão licenciada) suporta implantação **Distribuída/Cascata** e possui suporte a **Hot Standby** (redundância).
* **O que avalia no RAG**: Leitura de tabela comparativa entre software gratuito vs. pago.

---

### Q9. Especificações da Tabela DORI da Câmera VIP 7550
* **Pergunta**: Quais são as distâncias da tabela DORI da câmera VIP 7550 BD Z IA nas posições de lente Wide (W) e Telephoto (T)?
* **Dificuldade**: Média
* **Documento de Origem**: `Datasheet 7550 BD Z IA FT - V018_0.pdf` (Pág. 2)
* **Resposta Esperada (Gabarito)**:
  * **Wide (W)**: Detectar 64m | Observar 26m | Reconhecer 13m | Identificar 6,4m.
  * **Telephoto (T)**: Detectar 212m | Observar 85m | Reconhecer 42m | Identificar 21m.
* **O que avalia no RAG**: Capacidade de interpretar e formatar tabelas complexas de parâmetros ópticos (DORI).

---

### Q10. Funcionamento da Função SIP Hotspot no Telefone V3001
* **Pergunta**: Como funciona a função SIP Hotspot no telefone IP V3001 e qual a vantagem do seu uso?
* **Dificuldade**: Média
* **Documento de Origem**: `Manual_V3001_01-26_site.pdf` (Pág. 23 e 24)
* **Resposta Esperada (Gabarito)**: A função SIP Hotspot permite criar um grupo de toque (*ring group*) entre diferentes telefones compatíveis utilizando **apenas 1 conta SIP registrada** no ramal principal (modo Hotspot). Os demais telefones funcionam como clientes Hotspot sem necessidade de conta SIP individual registrada no PABX, expandindo a capacidade de ramais.
* **O que avalia no RAG**: Síntese de explicação conceitual e de arquitetura de rede VoIP.

---

### Q11. Diferença de Canais na Linha de Gravadores MHDX
* **Pergunta**: Qual a diferença de canais e tecnologia entre os gravadores MHDX 1104-C, MHDX 1108-C e MHDX 1116-C?
* **Dificuldade**: Média
* **Documento de Origem**: `Manual_MHDX_1104_1108_1116C_01-26_site.pdf` (Pág. 1 e 2)
* **Resposta Esperada (Gabarito)**: Todos pertencem à série de DVRs analógicos/HDCVI da Intelbras, porém variam na quantidade de canais físicos de vídeo: o **MHDX 1104-C** possui 4 canais, o **MHDX 1108-C** possui 8 canais e o **MHDX 1116-C** possui 16 canais.
* **O que avalia no RAG**: Agregação de variações de modelos dentro da mesma família de produtos.

---

### Q12. Suporte a DTMF no Telefone IP V3001
* **Pergunta**: Quais protocolos de transporte e de voz o telefone V3001 suporta para envio de DTMF nas chamadas SIP?
* **Dificuldade**: Média
* **Documento de Origem**: `Manual_V3001_01-26_site.pdf` (Pág. 5 e 21)
* **Resposta Esperada (Gabarito)**: Suporta 3 tipos de envio de DTMF: **In-band**, **Out-of-band (RFC 2833)** e **SIP INFO** (com envio de caracteres `#` e `*`).
* **O que avalia no RAG**: Leitura de opções de menu avançado de protocolo.

---

### Q13. Comportamento de Failback SIP no V3001
* **Pergunta**: O que acontece se a conexão do servidor SIP primário falhar no V3001 quando o "Ativar failback" estiver habilitado?
* **Dificuldade**: Média
* **Documento de Origem**: `Manual_V3001_01-26_site.pdf` (Pág. 20 e 21)
* **Resposta Esperada (Gabarito)**: Caso o telefone não obtenha resposta do Servidor SIP 1 (primário), ele tentará enviar automaticamente o pedido de registro ao **Servidor SIP 2 (secundário/backup)** configurado.
* **O que avalia no RAG**: Compreensão de regras condicionais e resiliência de rede.

---

### Q14. Codecs e Resoluções no Servidor iNVU 9164
* **Pergunta**: Quais são as resoluções de vídeo e codecs de áudio/vídeo suportados no gravador iNVU 9164 M2 IAX FT?
* **Dificuldade**: Média
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 2 e 3)
* **Resposta Esperada (Gabarito)**:
  * **Compressão de Vídeo**: H.265+, H.265, H.264+, H.264.
  * **Resoluções de Gravação**: 32 MP, 24 MP, 16 MP, 12 MP, 8 MP, 6 MP, 5 MP, 4 MP, 3 MP, 1080p, 960p, 720p, D1, CIF, QCIF.
* **O que avalia no RAG**: Extração de múltiplas listas de compatibilidade em datasheets.

---

## 🔴 Nível 3: Perguntas Difíceis & Casos Limite / RAG Negativo (6 Perguntas)

### Q15. Dimensionamento de Projeto InSearch para 30 Câmeras
* **Pergunta**: Uma empresa precisa implantar monitoramento com busca por linguagem natural (Ex: "encontrar pessoa com camisa vermelha") para 30 câmeras. O servidor iNVU 9164 M2 IAX FT sozinho atende essa demanda totalmente com InSearch local?
* **Dificuldade**: Difícil (Raciocínio Técnico & Limites)
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 1 e 4)
* **Resposta Esperada (Gabarito)**: **Não atende totalmente sozinho**. Embora o iNVU 9164 suporte 64 canais de vídeo e a função InSearch (busca por texto em linguagem natural), a capacidade máxima de processamento InSearch no próprio servidor é de até **16 canais**. Para atender as 30 câmeras com InSearch, é necessário utilizar câmeras IP que já possuam a inteligência InSearch embarcada ou adicionar servidores adicionais.
* **O que avalia no RAG**: Capacidade de cruzar o limite técnico (16 canais InSearch) com o requisito do projeto (30 câmeras).

---

### Q16. Uso do IP Utility como VMS / Gravador Principal
* **Pergunta**: O software IP Utility pode ser utilizado como o software principal para gravação contínua de vídeo das câmeras IP da Intelbras?
* **Dificuldade**: Difícil (Verificação de Escopo do Produto)
* **Documento de Origem**: `Manual_IP_Utility_01-26_site_4.pdf` (Pág. 2 e 6)
* **Resposta Esperada (Gabarito)**: **Não**. O IP Utility é um software secundário voltado exclusivamente para **auxiliar na localização e configuração de rede/imagem** dos dispositivos. O manual ressalta que ele não é um VMS/NVR para gerenciamento de gravação contínua. Para gravação, devem ser utilizados VMS como Defense IA ou gravadores NVR/DVR.
* **O que avalia no RAG**: Compreensão das limitações e papel arquitetural do produto.

---

### Q17. Envio de Mensagens SIP > 1500 bytes (TCP Automático)
* **Pergunta**: Como deve ser configurado o telefone V3001 caso o provedor SIP exija o protocolo TCP apenas para mensagens que ultrapassem 1500 bytes?
* **Dificuldade**: Difícil (Parâmetro Avançado de Rede)
* **Documento de Origem**: `Manual_V3001_01-26_site.pdf` (Pág. 21 - *TCP automático*)
* **Resposta Esperada (Gabarito)**: Deve-se habilitar a opção **"TCP automático"** nas configurações avançadas do SIP. Essa função faz com que o telefone utilize automaticamente o protocolo TCP para mensagens SIP cujo tamanho seja superior a 1500 bytes, mantendo o padrão para pacotes menores.
* **O que avalia no RAG**: Recuperação de regras específicas de pacotes MTU/SIP em manuais extensos.

---

### Q18. RAG Negativo / Indução de Falsa Característica (VIP 7550)
* **Pergunta**: O manual da câmera VIP 7550 BD Z IA especifica suporte nativo a reconhecimento facial com armazenamento de banco de dados de 100.000 faces na própria câmera?
* **Dificuldade**: Difícil (RAG Negativo / Checagem de Alucinação)
* **Documento de Origem**: `Datasheet 7550 BD Z IA FT - V018_0.pdf` (Pág. 2)
* **Resposta Esperada (Gabarito)**: **Não**. A VIP 7550 realiza *detecção de face*, contagem de pessoas e inteligência perimetral (DMI 3.0), mas **não possui banco de dados embarcado para 100.000 faces na câmera**. Bancos de dados de faces desse porte dependem de servidores dedicados ou softwares VMS como o Intelbras Defense IA. O LLM não deve inventar que a câmera guarda esse banco localmente.
* **O que avalia no RAG**: Testar se o sistema recusa ou corrige informações falsas/induzidas no prompt.

---

### Q19. Licenciamento e Alta Disponibilidade no Defense IA Lite
* **Pergunta**: Em uma solução com o Defense IA Lite (gratuito), é possível configurar um servidor secundário em *Hot Standby* para assumir automaticamente se o servidor principal cair?
* **Dificuldade**: Difícil (RAG Negativo & Licenciamento)
* **Documento de Origem**: `Comparativo de funções - Intelbras Defense IA & Lite - V1.pdf` (Pág. 3)
* **Resposta Esperada (Gabarito)**: **Não**. A função de *Hot Standby* e arquitetura distribuída/cascata é exclusiva da versão licenciada **Intelbras Defense IA**. A versão Lite (gratuita) opera estritamente em **Servidor Único** sem suporte a alta disponibilidade Hot Standby.
* **O que avalia no RAG**: Identificação de restrições de licenciamento em projetos de alta disponibilidade.

---

### Q20. Diferencial Tecnológico entre InSearch e Busca por IA Tradicional
* **Pergunta**: Qual a diferença entre a função InSearch e a busca por IA tradicional nos gravadores/servidores Intelbras conforme os manuais?
* **Dificuldade**: Difícil (Análise Conceitual e Diferencial Tecnológico)
* **Documento de Origem**: `Datasheet - iNVU 9164 M2 IAX FT.pdf` (Pág. 1 e 4)
* **Resposta Esperada (Gabarito)**: A busca IA tradicional baseia-se em metadados pré-categorizados (ex: selecionar "veículo" ou "pessoa" em filtros fixos). Já a função **InSearch** utiliza Inteligência Artificial por Linguagem Natural, permitindo realizar pesquisas descritivas via texto (ex: pesquisar características específicas de vestuário ou objetos) e criar eventos inteligentes baseados em texto livre.
* **O que avalia no RAG**: Síntese de novos recursos de IA descritos nos lançamentos e datasheets.

---

## 📋 Tabela Resumo para Execução de Benchmarks

| ID | Pergunta Resumida | Categoria | Documento Fonte | Métrica Chave Avaliada |
| :---: | :--- | :---: | :--- | :--- |
| **Q1** | Contas SIP no V3001 | 🟢 Fácil | `Manual_V3001_01-26_site.pdf` | Precision @ 1 |
| **Q2** | Canais de vídeo do iNVU 9164 | 🟢 Fácil | `Datasheet - iNVU 9164.pdf` | Precision @ 1 |
| **Q3** | Alcance IR da VIP 7550 | 🟢 Fácil | `Datasheet 7550.pdf` | Precision @ 1 |
| **Q4** | Função do IP Utility | 🟢 Fácil | `Manual_IP_Utility.pdf` | Conceptual Retrieval |
| **Q5** | Canais InSearch no iNVU 9164 | 🟢 Fácil | `Datasheet - iNVU 9164.pdf` | Numerical Limit |
| **Q6** | Resolução máxima iNVU 9164 | 🟢 Fácil | `Datasheet - iNVU 9164.pdf` | Numerical Value |
| **Q7** | Áreas DMI 3.0 na VIP 7550 | 🟢 Fácil | `Datasheet 7550.pdf` | Feature Limit |
| **Q8** | Defense IA vs Lite (Redundância) | 🟡 Média | `Comparativo Defense IA.pdf` | Table Comparative |
| **Q9** | Tabela DORI VIP 7550 (Wide vs Tele) | 🟡 Média | `Datasheet 7550.pdf` | Multiline Table Format |
| **Q10** | Funcionamento SIP Hotspot no V3001 | 🟡 Média | `Manual_V3001.pdf` | Multi-paragraph Synthesis |
| **Q11** | Diferença de canais linha MHDX | 🟡 Média | `Manual_MHDX.pdf` | Aggregation across models |
| **Q12** | Tipos de DTMF no V3001 | 🟡 Média | `Manual_V3001.pdf` | List Extraction |
| **Q13** | Comportamento Failback SIP V3001 | 🟡 Média | `Manual_V3001.pdf` | Conditional Logic |
| **Q14** | Codecs e resoluções do iNVU 9164 | 🟡 Média | `Datasheet - iNVU 9164.pdf` | Full Specs Extraction |
| **Q15** | InSearch 30 câmeras no iNVU 9164 | 🔴 Difícil | `Datasheet - iNVU 9164.pdf` | System Architecture / Limits |
| **Q16** | IP Utility como VMS de gravação | 🔴 Difícil | `Manual_IP_Utility.pdf` | Negative Boundary |
| **Q17** | Mensagens SIP > 1500 bytes (TCP) | 🔴 Difícil | `Manual_V3001.pdf` | Advanced Tech Rule |
| **Q18** | Banco de 100k faces na VIP 7550 | 🔴 Difícil | `Datasheet 7550.pdf` | Hallucination Rejection |
| **Q19** | Hot Standby no Defense IA Lite | 🔴 Difícil | `Comparativo Defense IA.pdf` | License Boundary |
| **Q20** | InSearch vs IA Tradicional | 🔴 Difícil | `Datasheet - iNVU 9164.pdf` | Deep Tech Conceptualization |

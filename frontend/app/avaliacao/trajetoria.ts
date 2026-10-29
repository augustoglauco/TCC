/** Narrativa do modal "Trajetória completa" da /avaliacao: do plano inicial às conclusões. Fonte: docs/EVALUATION.md. */
export interface Capitulo {
  titulo: string;
  paragrafos: string[];
  itens?: string[];
  tabela?: { colunas: string[]; linhas: string[][] };
}

export const TRAJETORIA: Capitulo[] = [
  {
    titulo: "1. O ponto de partida",
    paragrafos: [
      "A pergunta do TCC é se um assistente com roteador, RAG e modelo local numa GPU de 16 GB atende bem os quatro domínios (Vendas, Suporte, Atendimento ao Usuário e Agendamento). Quatro avaliações foram planejadas: acerto do roteador, qualidade do RAG, latência local × externo e resistência a prompt injection.",
      "Decidimos medir só depois que as dependências existiam (corpus ingerido, sistema completo), em uma medição única, em vez de testar peças isoladas que mudariam depois.",
      "As primeiras versões dos conjuntos (40 mensagens de roteador, 18 perguntas de RAG, 8 casos de injeção) foram montadas sobre outros documentos e eram pequenas demais. Em 2026-10-17 foram substituídas, e nenhum resultado anterior a essa data vale.",
    ],
  },
  {
    titulo: "2. Os conjuntos de teste",
    paragrafos: [
      "O corpus são os manuais do fornecedor (ControlId), com 667.291 caracteres úteis. Os rascunhos de perguntas foram gerados a partir do texto dos PDFs e revisados um a um pelo dono em /admin/datasets (aprovar, corrigir ou descartar). Os descartados ficam no arquivo mas não entram em nenhum número.",
      "O gabarito do RAG de documentos é ponderado pelo volume de texto de cada produto: cota igual por pasta geraria perguntas artificiais. Há também perguntas sem resposta no corpus, para medir se o assistente admite que não sabe.",
    ],
    tabela: {
      colunas: ["Conjunto", "Itens válidos", "Origem do gabarito"],
      linhas: [
        ["Roteador", "311 (229 não ambíguos + 82 ambíguos)", "rascunho por LLM + revisão do dono"],
        [
          "RAG documentos",
          "252 (226 com resposta + 26 sem); as rodadas usam 222 + 26",
          "rascunho a partir dos PDFs + revisão",
        ],
        ["RAG imagem", "72 (23 positivos + 49 negativos)", "nome da pasta do fornecedor"],
        ["RAG banco", "80", "template a partir das linhas do banco"],
        [
          "Injeção de prompt",
          "95 (45 diretos + 50 indiretos)",
          "rascunho por LLM + revisão do dono",
        ],
      ],
    },
  },
  {
    titulo: "3. Como comparar: a estatística",
    paragrafos: [
      "Com amostras desta ordem, o intervalo de confiança de 95% (Wilson) de uma taxa ainda é largo: “95% contra 90%” é empate. Por isso o IC descreve cada resultado isolado, mas a comparação entre candidatos é pareada, porque todos respondem aos mesmos itens.",
    ],
    itens: [
      "McNemar exato para acerto/erro (roteador, injeção, imagem): só conta os itens em que dois candidatos discordam.",
      "Wilcoxon pareado para notas de 1 a 5. No RAG o McNemar sobre “fonte correta” foi inútil (a busca é idêntica entre modelos), então a comparação passou a ser a nota.",
      "Correção de Bonferroni para os 6 pares de 4 modelos: só vale p < 0,0083.",
      "Seed fixa (42) nas comparações entre modelos, para a comparação ser reproduzível.",
    ],
  },
  {
    titulo: "4. Os modelos iniciais e a eliminação",
    paragrafos: [
      "Dez modelos locais foram baixados como candidatos. O Llama 3.2 Vision foi descartado antes de ser medido: o Ollama usado (0.30.6) não tem mais a arquitetura dele, e as duas versões testadas falharam do mesmo jeito. Restaram 9.",
      "O critério de corte foi escrito antes de qualquer número existir, para não virar escolha a posteriori: rodar até o fim em até 15 GB de VRAM; no máximo 10% de respostas com JSON inválido; p95 de até 30 s; e, dos que passam, ficar a até 10 pontos percentuais do melhor no roteador; teto de 5 sobreviventes.",
      "A triagem usou só roteador e imagem (sem juiz, custo zero) e levou cerca de 75 minutos. Ninguém caiu por VRAM ou latência: todo o corte veio do formato JSON e da acurácia.",
    ],
    tabela: {
      colunas: ["Modelo", "Roteador", "JSON inválido", "Resultado"],
      linhas: [
        ["gemma4-12b-q4", "85,2%", "0%", "sobrevivente"],
        ["gemma4-e4b-q8", "84,7%", "0%", "sobrevivente"],
        ["qwen25-vl-3b", "79,9%", "6,5%", "sobrevivente"],
        ["qwen25-vl-7b", "77,3%", "0%", "sobrevivente"],
        ["gemma3-gaia-4b-f16", "72,9%", "5,2%", "cortado (2,3 pp abaixo da linha de 75,2%)"],
        ["qwen35-9b", "62,9%", "39,0%", "cortado (JSON)"],
        ["phi4-mini-bf16", "50,7%", "90,9%", "cortado (JSON)"],
        ["deepseek-r1-distill-8b-q8", "48,5%", "100%", "cortado (JSON)"],
        ["qwen35-9b-defiant-fable-mtp", "48,5%", "100%", "cortado (JSON)"],
      ],
    },
  },
  {
    titulo: "5. O roteador: como as definições e a pontuação mudaram",
    paragrafos: [
      "O roteador foi desenhado em três camadas, comparadas entre si: heurística de palavras-chave, heurística com LLM local e um modelo externo como referência. Reconhecemos que o conjunto antigo mal chegava ao LLM (só 9 de 40 mensagens), então o conjunto atual foi desenhado para que a maioria (231 de 311) dependa do modelo.",
    ],
    itens: [
      "Duas taxas separadas: acurácia do sistema (heurística + LLM) e acurácia do modelo no subconjunto que chega a ele.",
      "Mensagens ambíguas passaram a ser multi-rótulo (aceita qualquer domínio plausível do par) e têm placar próprio, fora do principal.",
      "Em 2026-10-20 o dono fixou as definições dos domínios (por exemplo: atendimento é pós-compra ou dúvida geral sobre a empresa; compatibilidade isolada é suporte, mas junto com intenção de compra é vendas; agendamento inclui os motivos de visita) e as colocou no classificador e no gerador.",
      "Nessa mesma data o conjunto foi reavaliado: 60 casos fracos ou mal rotulados foram descartados e alguns de compatibilidade e de remarcação foram restaurados.",
      "fora_escopo passou a ser rótulo e linha da matriz de confusão, porque também é gabarito.",
    ],
  },
  {
    titulo: "6. O RAG: separar a busca da resposta",
    paragrafos: [
      "Três medições antes de qualquer varredura mudaram o plano: o modelo de embedding original (MiniLM) tinha janela de 128 tokens e descartava cerca de 31% de cada chunk de 800 caracteres, sem erro; ele era o 93º de 93 no benchmark MTEB-BR; e o corpus é pequeno demais para que índice HNSW ou quantização façam diferença (a busca já é exata).",
      "Em vez de acoplar busca e juiz LLM em cada configuração (caro e sujeito a rate limit), a busca passou a ser medida offline pelo documento de origem do gabarito, sem chamar API: Recall@k, nDCG@10 (métrica principal), MRR e taxa de resultado vazio. O juiz LLM só volta uma vez, na Etapa 7, para confirmar que o ganho virou ganho de resposta.",
    ],
    tabela: {
      colunas: ["Etapa", "O que variou", "Resultado e decisão"],
      linhas: [
        [
          "0 Auditoria do corpus",
          "—",
          "mede texto útil por PDF; achou PDFs sem texto aproveitável",
        ],
        ["1 Baseline", "—", "instrumento de recuperação sobre 163 perguntas"],
        [
          "2 Embedding",
          "4 modelos",
          "bge-m3 ≈ embeddinggemma ≫ e5 ≫ MiniLM; escolhido bge-m3 (cabe ao lado do gerador de 12B)",
        ],
        [
          "3 Chunking",
          "grade 5×3 em tokens",
          "512 a 1024 empatam; adotado 768 tokens com 15% de overlap, sem vender como superior aos vizinhos",
        ],
        [
          "4 top_k e limiar",
          "varredura offline",
          "nenhum limiar separa respondíveis de não respondíveis; top_k 5; limiar 0,35 mantido (0,60 rejeitado)",
        ],
        [
          "5 Distância e índice",
          "cosine/dot/euclidiana",
          "cosine mantido; índice extra não criado",
        ],
        [
          "6 HNSW/quantização",
          "—",
          "resultado negativo registrado: efeito zero neste tamanho de corpus",
        ],
        [
          "7 Confirmação com juiz",
          "baseline × vencedora",
          "nota 2,74 → 4,14; fonte correta 156 → 213",
        ],
      ],
    },
  },
  {
    titulo: "7. A geração: prompt, recusa e top_k",
    paragrafos: [
      "Um achado importante veio da recusa: nenhum limiar de score separa pergunta respondível de não respondível, e com o contexto vazio nada mandava o modelo recusar. A recusa teve de ser tratada no prompt. Cada ajuste foi medido pareado contra o anterior, nas mesmas perguntas e com o mesmo juiz e gerador.",
    ],
    tabela: {
      colunas: ["Ajuste", "Medição", "Decisão"],
      linhas: [
        [
          "Rotular trechos com [Fonte: arquivo] e mandar citar",
          "uso da fonte 3,01 → 3,71 (p<0,001); correção factual sem mudança significativa",
          "adotado (ressalva: “uso da fonte” mede citação, que o prompt pede)",
        ],
        [
          "Prompt de recusa v2 (“diga que não encontrou” em vez de “responda com o que souber”)",
          "nas 26 sem resposta: recusou 14 → 19, alucinou 19 → 13; nas respondíveis, neutro",
          "adotado",
        ],
        [
          "Variante C (regras extras de geração)",
          "nota 3,90 → 3,95, sem diferença significativa (p=0,38)",
          "não adotada: indistinguível de ruído",
        ],
        [
          "top_k 3 → 5",
          "nota 3,87 → 4,00 (p=0,017); fonte correta 203 → 213; prompt +56% de tokens",
          "adotado",
        ],
        [
          "Limiar 0,35 → 0,60",
          "recusava mais, mas 8,4% das perguntas respondíveis voltavam vazias",
          "rejeitado",
        ],
      ],
    },
  },
  {
    titulo: "8. O juiz e o contexto: dois erros que viraram correção",
    paragrafos: [
      "O juiz começou no nível gratuito do OpenRouter, por decisão de custo, com um modelo pequeno para a tarefa. As rodadas oficiais a partir de 2026-10-25 passaram a usar claude-haiku-5.5 como juiz. Em todos os casos o juiz é externo e diferente do modelo avaliado.",
      "Na primeira rodada completa dos 4 modelos, as notas saíram todas 1 e as respostas vinham como “Com”. Não era o juiz: o Ollama usava contexto de 4096 tokens e truncava em silêncio o prompt de cerca de 4,7 mil tokens (5 trechos de 768 tokens). A rodada foi descartada, o num_ctx passou a 8192, inclusive em produção, e tudo foi refeito. Os números da Etapa 7 não foram afetados porque aquele script já usava 8192.",
      "Outra correção de método: as rodadas “completas” de RAG e injeção incluíam por padrão os casos descartados na revisão (283 e 100 casos). O filtro foi corrigido e os resultados foram refiltrados para 222 + 26 e 95 casos.",
    ],
  },
  {
    titulo: "9. A rodada final",
    paragrafos: [
      "Os 4 sobreviventes rodaram as quatro etapas (roteador, RAG, injeção e imagem) com o sistema completo, resumida por eval/model_benchmark/consolidar.py com os testes pareados e a correção de Bonferroni. Em seguida foram medidas a latência (60 mensagens × 3 repetições, local × externo, com custo em dólar do externo) e as avaliações de produção que alimentam esta página.",
      "A comparação entre os modelos aparece nos gráficos da seção “Comparativo de modelos locais”. Os melhores pontos da qualidade × latência são os dois Gemma 4; os Qwen2.5-VL ficam bem abaixo em nota de RAG.",
    ],
  },
  {
    titulo: "10. Limitações e próximos passos",
    paragrafos: ["O que estes resultados não provam:"],
    itens: [
      "Os conjuntos são sintéticos e revisados por uma pessoa; essa pessoa pode ter sido induzida nas aprovações pelos rascunhos do LLM.",
      "A avaliação cobre um único perfil de collection de texto, com um único corpus.",
      "Imagem: poucos positivos (23); o resultado é indício, não medida.",
      "Respostas inventadas nas perguntas sem resposta no corpus continuam um problema: o prompt v2 reduziu, mas não eliminou.",
      "Cada comparação de modelos é de uma execução com seed fixa; não mede a variação entre execuções.",
      "Próximo passo planejado: refazer a ingestão com os documentos tratados em Markdown, as fotos pelas telas do sistema e preços reais, e comparar com a ingestão atual no mesmo conjunto de perguntas.",
    ],
  },
];

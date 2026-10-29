/** Texto do modal "detalhes" de cada gráfico da /avaliacao (motivo, relevância, cuidados e caminho até a conclusão). */
export interface Detalhe {
  motivo: string;
  relevancia: string;
  consideracoes: string[];
  trajetoria: string;
}

const METODO =
  "Todas as avaliações seguem o mesmo critério: o instrumento só foi medido depois que as dependências existiam (uma medição única e holística, não testes parciais), as perguntas foram escritas a partir dos documentos e revisadas uma a uma em /admin/datasets (as descartadas ficam fora dos números) e as barras de erro são intervalos de Wilson de 95%.";

export const DETALHES: Record<string, Detalhe> = {
  qualidadeLatencia: {
    motivo:
      "A decisão local × externo e a escolha do modelo local são um compromisso entre qualidade e tempo de resposta: um modelo melhor costuma ser mais lento na GPU de 16 GB.",
    relevancia:
      "É o gráfico que escolhe o modelo local do sistema. Quem está no canto superior esquerdo responde bem e rápido; fora dele, a escolha vira uma troca explícita.",
    consideracoes: [
      "A nota vem do juiz externo (claude-haiku-5.5), diferente do modelo que gera, para evitar que um modelo se favoreça ao se julgar.",
      "Só entram os modelos que rodaram a etapa de RAG completa; os eliminados na triagem não têm ponto.",
      "A latência p95 é a do pior caso comum (95% das respostas saem antes disso) e depende da GPU usada na medição.",
    ],
    trajetoria:
      "Partimos de 10 modelos candidatos, uma triagem barata os reduziu a 4 e só esses fizeram a rodada completa. A primeira rodada foi descartada: o contexto padrão do Ollama (4096 tokens) truncava o prompt de RAG e o modelo respondia “Com”. Com num_ctx 8192 a rodada foi refeita.",
  },
  roteadorInjecaoModelos: {
    motivo:
      "O modelo local precisa fazer bem duas tarefas além de responder: classificar a intenção (roteador) e não obedecer instruções maliciosas.",
    relevancia:
      "Mostra se o vencedor em qualidade não é frágil em segurança ou em roteamento. Um modelo bom de RAG que erra a rota ou cede a ataques não serve ao sistema.",
    consideracoes: [
      "Diferenças pequenas com poucas amostras são acaso; por isso a decisão usa testes pareados (McNemar exato) e correção de Bonferroni para os 6 pares de modelos (significativo apenas se p < 0,0083).",
      "Os dois conjuntos de perguntas são os mesmos para todos os modelos, o que torna a comparação pareada.",
    ],
    trajetoria:
      "O roteador e a injeção começaram como avaliações do sistema em produção; o benchmark repete as mesmas perguntas com cada modelo candidato trocado como gerador. " +
      METODO,
  },
  resumoModelos: {
    motivo:
      "Os gráficos mostram a forma; a tabela guarda os números exatos para citar no texto do TCC.",
    relevancia: "É a fonte de cada ponto e barra dos gráficos de modelos.",
    consideracoes: [
      "A cor ao lado do nome é a do ponto no gráfico de qualidade × latência.",
      "O custo em dólares do modelo externo é calculado a partir do preço configurado (US$ 0,10 por milhão de tokens de entrada e US$ 0,50 de saída).",
    ],
    trajetoria:
      "O relatório completo, com os testes pareados entre todos os pares, é gerado por eval/model_benchmark/consolidar.py.",
  },
  roteadorAcuracia: {
    motivo:
      "O roteador decide para qual domínio (Vendas, Suporte, Atendimento ao Usuário ou Agendamento) a conversa vai. Um erro aqui manda o cliente para o playbook errado.",
    relevancia:
      "Compara três formas de decidir, da mais barata à mais cara, e responde se vale usar um LLM para isso ou se palavras-chave bastam.",
    consideracoes: [
      "Se as barras de erro de dois métodos se sobrepõem, a diferença pode ser acaso com essa amostra.",
      "A acurácia mede o domínio, não a qualidade da resposta final.",
    ],
    trajetoria:
      "O roteador foi desenhado em camadas: heurística de palavras-chave (instantânea, sem GPU), heurística com LLM local para os casos ambíguos e um modelo externo como referência de comparação. A avaliação mede quanto cada camada acrescenta. " +
      METODO,
  },
  matrizConfusao: {
    motivo: "Mostra onde o roteador erra, não só quanto: quais domínios são confundidos entre si.",
    relevancia:
      "Orienta a correção: erros concentrados em um par de domínios indicam ajustar o critério ou o prompt daquele par, em vez de trocar o método inteiro.",
    consideracoes: [
      "Cada linha soma os casos reais de um domínio; a diagonal são os acertos.",
      "Células fora da diagonal com poucos casos podem ser ruído.",
    ],
    trajetoria: "Acompanha a acurácia por método: a mesma rodada gera a matriz de cada provedor.",
  },
  distribuicaoNotas: {
    motivo:
      "A média esconde falhas: uma média 4 pode vir de muitas notas 4 ou de muitos 5 com alguns 1.",
    relevancia:
      "Mostra a proporção de respostas boas e o tamanho da cauda de falhas (notas 1 e 2).",
    consideracoes: [
      "O juiz é um LLM comparando a resposta ao gabarito escrito à mão a partir do documento; ele pode errar, por isso foi usado um juiz externo e diferente do gerador.",
      "As perguntas sem resposta no corpus ficam fora desta distribuição e têm cartões próprios.",
    ],
    trajetoria:
      "A avaliação do RAG evoluiu em etapas (0 a 7): primeiro medimos só a recuperação, depois a resposta com juiz. " +
      METODO,
  },
  dificuldade: {
    motivo: "Verifica se o sistema só acerta o que é fácil.",
    relevancia: "Barras parecidas indicam que o desempenho não depende do nível da pergunta.",
    consideracoes: [
      "A dificuldade é atribuída na criação da pergunta, não medida a posteriori.",
      "Faixas com poucas perguntas têm nota instável.",
    ],
    trajetoria:
      "Cada pergunta do conjunto traz o campo de dificuldade; a nota média é agrupada por ele.",
  },
  etapa7Fonte: {
    motivo:
      "Prova, com o mesmo conjunto de perguntas e o mesmo juiz, que a configuração escolhida recupera mais documentos certos que o ponto de partida.",
    relevancia:
      "É o resultado central do RAG: a melhora de recuperação que justifica a configuração em produção (bge-m3, chunks de 768 tokens com 115 de sobreposição, top_k 5, limiar 0,35, prompt v2).",
    consideracoes: [
      "Sem sobreposição dos intervalos de 95%, a melhora é real, não acaso.",
      "A comparação é válida porque só muda a configuração da busca; perguntas e juiz são fixos.",
    ],
    trajetoria:
      "Começamos com MiniLM e chunks de 800 caracteres. As Etapas 1 a 6 compararam embeddings, tamanhos de chunk, limiar, top_k e distância sobre a métrica de recuperação (rápida e sem LLM). A Etapa 7 confirmou o vencedor com o juiz LLM, que é a medida que importa ao cliente.",
  },
  etapa7Nota: {
    motivo:
      "Recuperar o documento certo só vale se a resposta melhora; este gráfico liga a busca ao que o cliente lê.",
    relevancia:
      "As “recusas indevidas” (disse que não achou, mas a resposta existia) eram o pior sintoma da busca antiga: o cliente era mandado ao atendente sem necessidade.",
    consideracoes: [
      "A recusa é detectada por padrões de texto (“não encontrei”, “atendente”, “não consta”), então é uma estimativa, não leitura humana.",
      "A latência subiu um pouco com mais contexto no prompt (ver tabela).",
    ],
    trajetoria:
      "Durante a Etapa 7 descobrimos que o contexto padrão de 4096 tokens do Ollama truncava silenciosamente o prompt de cinco trechos de 768 tokens; fixar num_ctx em 8192 corrigiu o sistema em produção.",
  },
  resumoEtapa7: {
    motivo:
      "Reúne em um quadro os números do antes e do depois, incluindo o que os gráficos não mostram.",
    relevancia:
      "A recusa correta nas perguntas sem resposta e a latência mostram o custo e o efeito colateral da melhora.",
    consideracoes: [
      "Nas perguntas sem resposta no corpus, o número de respostas inventadas praticamente não mudou (10 para 11 casos): continua sendo uma limitação declarada.",
    ],
    trajetoria:
      "Gerado por eval/rag_quality/consolidar_etapa7.py a partir dos resultados das duas rodadas.",
  },
  chunkSize: {
    motivo:
      "O tamanho do pedaço de texto define o que a busca consegue encontrar: pedaços pequenos perdem contexto, grandes diluem o assunto.",
    relevancia:
      "Justifica o tamanho de chunk adotado com dados, em vez de um valor herdado de tutorial.",
    consideracoes: [
      "Cada ponto usa o melhor overlap daquele tamanho (grade de tamanhos × overlaps).",
      "Curvas planas indicam que o tamanho importa pouco; a escolha final também considera o limite de contexto do modelo.",
    ],
    trajetoria:
      "Foi a Etapa 3 da otimização de ingestão. A escolha foi depois confirmada, de ponta a ponta, na Etapa 7 com o juiz LLM.",
  },
  injecaoResistencia: {
    motivo:
      "Um assistente que atende o público e lê documentos precisa resistir a instruções maliciosas, na mensagem do usuário ou escondidas em um documento recuperado.",
    relevancia: "Mede o risco de segurança específico de sistemas com LLM e RAG.",
    consideracoes: [
      "A resistência alta não prova segurança: mede apenas os ataques do conjunto de casos.",
      "O modelo externo serve de referência para o local.",
    ],
    trajetoria:
      "O conjunto de casos de injeção foi escrito e revisado como os demais (95 casos revisados). Segue a especificação de segurança de 2026-10-07.",
  },
  injecaoCategorias: {
    motivo:
      "Separa onde o ataque está: direto, na mensagem, ou indireto, dentro de um documento do RAG.",
    relevancia:
      "A injeção indireta é a mais perigosa em produção, porque o usuário não precisa escrever nada malicioso.",
    consideracoes: [
      "“Comprometidos” é quantas vezes o modelo obedeceu ao ataque; menos é melhor.",
      "Categorias com poucos casos têm taxa instável.",
    ],
    trajetoria: "As categorias são as do conjunto de casos de injeção.",
  },
};

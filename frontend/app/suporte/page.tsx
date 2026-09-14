// MVP: FAQ estático — conteúdo fixo no componente, sem chamada à API. É
// justamente este tipo de conteúdo que o crawler (R4) e o RAG de
// Suporte/Atendimento (R7) devem indexar mais adiante (ver docs/ROADMAP.md,
// Fase 2/3); aqui ele existe apenas para a página ter conteúdo real.
const FAQ_ITEMS = [
  {
    question: "Como acompanho o status do meu pedido?",
    answer:
      'Acesse "Pedidos > Histórico de pedidos" com sua conta ou pergunte ao assistente virtual informando o número do pedido.',
  },
  {
    question: "Qual o prazo de garantia dos equipamentos?",
    answer:
      "A garantia padrão é de 12 meses contra defeitos de fabricação, salvo indicação diferente no manual do produto.",
  },
  {
    question: "Como solicito o manual técnico de um equipamento?",
    answer:
      "Os manuais estão disponíveis na página de detalhe de cada produto ou podem ser solicitados diretamente ao assistente virtual.",
  },
  {
    question: "Como faço para agendar uma visita técnica?",
    answer:
      "Converse com o assistente virtual e peça o agendamento de uma visita — ele coleta data, horário e dados básicos e confirma via e-mail.",
  },
  {
    question: "Quais formas de pagamento são aceitas?",
    answer: "Boleto bancário, cartão de crédito e faturamento para clientes cadastrados.",
  },
  {
    question: "Como faço para falar com um atendente humano?",
    answer:
      "Durante a conversa com o assistente virtual, peça para falar com um atendente; casos identificados como urgentes também são encaminhados automaticamente.",
  },
];

export default function SuportePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Central de Ajuda</h1>
      <p className="mt-2 text-gray-600">
        Perguntas frequentes sobre pedidos, garantia, manuais e agendamento.
      </p>

      <dl className="mt-8 space-y-6">
        {FAQ_ITEMS.map((item) => (
          <div key={item.question} className="border-b border-gray-200 pb-6">
            <dt className="font-medium text-gray-900">{item.question}</dt>
            <dd className="mt-2 text-gray-600">{item.answer}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

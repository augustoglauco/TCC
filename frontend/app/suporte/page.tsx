"use client";

import { useChatStore } from "@/lib/hooks/useChatStore";

// MVP: FAQ estático — conteúdo fixo no componente, sem chamada à API. É
// justamente este tipo de conteúdo que o crawler (R4) e o RAG de
// Suporte/Atendimento (R7) devem indexar mais adiante (ver docs/ROADMAP.md,
// Fase 2/3); aqui ele existe apenas para a página ter conteúdo real.
const FAQ_ITEMS = [
  {
    category: "Pedidos",
    question: "Como acompanho o status do meu pedido?",
    answer:
      'Acesse "Pedidos > Histórico de pedidos" com sua conta ou pergunte ao assistente virtual informando o número do pedido.',
  },
  {
    category: "Garantia",
    question: "Qual o prazo de garantia dos equipamentos?",
    answer:
      "A garantia padrão é de 12 meses contra defeitos de fabricação, salvo indicação diferente no manual do produto.",
  },
  {
    category: "Manuais",
    question: "Como solicito o manual técnico de um equipamento?",
    answer:
      "Os manuais estão disponíveis na página de detalhe de cada produto ou podem ser solicitados diretamente ao assistente virtual.",
  },
  {
    category: "Agendamento",
    question: "Como faço para agendar uma visita técnica?",
    answer:
      "Converse com o assistente virtual e peça o agendamento de uma visita — ele coleta data, horário e dados básicos e confirma via e-mail.",
  },
  {
    category: "Pagamentos",
    question: "Quais formas de pagamento são aceitas?",
    answer: "Boleto bancário, cartão de crédito e faturamento para clientes cadastrados.",
  },
  {
    category: "Atendimento",
    question: "Como faço para falar com um atendente humano?",
    answer:
      "Durante a conversa com o assistente virtual, peça para falar com um atendente; casos identificados como urgentes também são encaminhados automaticamente.",
  },
];

export default function SuportePage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho da página */}
      <div className="border-b border-slate-200 pb-6">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          <span>🔧</span> Central de Ajuda & FAQ
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Como podemos ajudar você hoje?
        </h1>
        <p className="mt-2 text-sm text-slate-600 sm:text-base">
          Encontre respostas rápidas sobre pedidos, garantia, manuais e agendamento de visitas.
        </p>
      </div>

      {/* Lista de Perguntas Frequentes em cards modernos */}
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {FAQ_ITEMS.map((item) => (
          <div
            key={item.question}
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:border-blue-300 hover:shadow-md"
          >
            <div>
              <span className="inline-block rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                {item.category}
              </span>
              <dt className="mt-3 text-base font-bold text-slate-900 leading-snug">{item.question}</dt>
              <dd className="mt-2 text-xs sm:text-sm text-slate-600 leading-relaxed">{item.answer}</dd>
            </div>
          </div>
        ))}
      </dl>

      {/* Banner de ajuda do Chat */}
      <div className="rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50 to-indigo-50 p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-blue-950">Não encontrou o que procurava?</h2>
          <p className="text-xs sm:text-sm text-blue-800 mt-1">
            Nosso assistente virtual inteligente está disponível 24 horas por dia no canto inferior direito.
          </p>
        </div>
        <button
          type="button"
          onClick={() => useChatStore.getState().open()}
          className="whitespace-nowrap rounded-lg bg-blue-600 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors cursor-pointer"
        >
          Perguntar ao Chat 💬
        </button>
      </div>
    </div>
  );
}


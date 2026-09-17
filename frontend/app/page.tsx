import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-14 space-y-12">
      {/* 🚀 Hero Section */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-6 sm:p-10 text-white shadow-xl">
        <div className="relative z-10 max-w-3xl space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-300 ring-1 ring-inset ring-blue-500/20">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
            </span>
            Assistente Virtual Multimodal IA
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight sm:text-5xl leading-tight">
            Atendimento Inteligente para{" "}
            <span className="bg-gradient-to-r from-blue-400 via-indigo-300 to-sky-300 bg-clip-text text-transparent">
              Equipamentos Industriais
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl">
            Distribuidora de equipamentos e peças industriais. Protótipo de TCC integrado com
            inferência local em GPU (16GB), RAG vetorial híbrido, entrada multimodal (texto, áudio e imagem)
            e suporte a protocolo MCP (Google Calendar & Provedor B2B).
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <a
              href="#chat-widget"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-md transition-all hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              <span>Conversar com o Assistente</span>
              <span className="text-base">💬</span>
            </a>
            <Link
              href="/produtos"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-800/80 px-5 py-3 text-sm font-semibold text-slate-200 backdrop-blur-xs transition-all hover:bg-slate-700 hover:text-white"
            >
              <span>Explorar Catálogo</span>
              <span className="text-base">📦</span>
            </Link>
          </div>
        </div>

        {/* Efeito decorativo sutil de fundo */}
        <div aria-hidden="true" className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-blue-600/20 blur-3xl" />
        <div aria-hidden="true" className="absolute -left-20 -bottom-20 h-72 w-72 rounded-full bg-indigo-600/20 blur-3xl" />
      </section>

      {/* 🎯 Os 4 Domínios de Atendimento */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-slate-200 pb-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
              Domínios de Atendimento Especiais
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1">
              O Roteador inteligente classifica a intenção da mensagem e aciona a camada especialista adequada.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* Card Vendas */}
          <div className="group rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:-translate-y-1 hover:border-blue-300 hover:shadow-md">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-xl text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
              🛍️
            </div>
            <h3 className="mt-4 font-bold text-slate-900">Vendas & Cotações</h3>
            <p className="mt-2 text-xs text-slate-600 leading-relaxed">
              Consulta de estoque em tempo real, especificações técnicas, cotações e reservas via MCP B2B.
            </p>
          </div>

          {/* Card Suporte Técnico */}
          <div className="group rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:-translate-y-1 hover:border-indigo-300 hover:shadow-md">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-xl text-indigo-600 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
              🔧
            </div>
            <h3 className="mt-4 font-bold text-slate-900">Suporte Técnico</h3>
            <p className="mt-2 text-xs text-slate-600 leading-relaxed">
              Resolução de dúvidas sobre instalação, erros e manuais usando busca semântica RAG.
            </p>
          </div>

          {/* Card Atendimento */}
          <div className="group rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:-translate-y-1 hover:border-sky-300 hover:shadow-md">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-50 text-xl text-sky-600 group-hover:bg-sky-600 group-hover:text-white transition-colors">
              💬
            </div>
            <h3 className="mt-4 font-bold text-slate-900">Atendimento Geral</h3>
            <p className="mt-2 text-xs text-slate-600 leading-relaxed">
              Informações institucionais, horários de funcionamento, garantia e políticas da empresa.
            </p>
          </div>

          {/* Card Agendamento */}
          <div className="group rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:-translate-y-1 hover:border-emerald-300 hover:shadow-md">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-xl text-emerald-600 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
              📅
            </div>
            <h3 className="mt-4 font-bold text-slate-900">Agendamento de Visita</h3>
            <p className="mt-2 text-xs text-slate-600 leading-relaxed">
              Marcação e confirmação automatizada de reuniões integradas diretamente ao Google Calendar.
            </p>
          </div>
        </div>
      </section>

      {/* 🛠️ Funcionalidades & Arquitetura */}
      <section className="rounded-2xl border border-slate-200 bg-slate-50/80 p-6 sm:p-8 space-y-6">
        <h2 className="text-lg sm:text-xl font-bold text-slate-900">
          Recursos Multimodais & Arquitetura Agêntica
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-white p-4 border border-slate-200/80">
            <div className="text-xl">🎙️ Áudio (Whisper)</div>
            <p className="mt-1.5 text-xs text-slate-600">
              Gravação de voz com transcrição automática (Speech-to-Text) enviada diretamente para contextualização do assistente.
            </p>
          </div>

          <div className="rounded-lg bg-white p-4 border border-slate-200/80">
            <div className="text-xl">🖼️ Visão & OCR (CLIP)</div>
            <p className="mt-1.5 text-xs text-slate-600">
              Reconhecimento de texto em fotos de placas/comprovantes e busca vetorial por similaridade de imagem.
            </p>
          </div>

          <div className="rounded-lg bg-white p-4 border border-slate-200/80">
            <div className="text-xl">⚡ Roteamento Híbrido</div>
            <p className="mt-1.5 text-xs text-slate-600">
              Decisão automática entre inferência em GPU local (16GB), RAG vetorial ou transbordo para modelo externo.
            </p>
          </div>
        </div>
      </section>

      {/* 🔗 Acesso Rápido às Seções */}
      <section className="space-y-4">
        <h2 className="text-lg sm:text-xl font-bold text-slate-900">Navegação Rápida</h2>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 text-sm">
          <Link
            href="/produtos"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">📦</span>
            <span>Produtos</span>
          </Link>

          <Link
            href="/pedidos"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">🛒</span>
            <span>Pedidos</span>
          </Link>

          <Link
            href="/agendamentos"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">📅</span>
            <span>Agendamentos</span>
          </Link>

          <Link
            href="/suporte"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">🔧</span>
            <span>Suporte</span>
          </Link>

          <Link
            href="/admin/ingestao"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">📄</span>
            <span>Ingestão RAG</span>
          </Link>

          <Link
            href="/admin/modelos"
            className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-4 text-center font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/50 hover:text-blue-700 transition-all"
          >
            <span className="text-2xl mb-1">🤖</span>
            <span>Modelos IA</span>
          </Link>
        </div>
      </section>
    </div>
  );
}

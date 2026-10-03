"use client";

import { Modal } from "@/components/ui/Modal";

export interface PlaygroundManualModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PlaygroundManualModal({ open, onOpenChange }: PlaygroundManualModalProps) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      size="2xl"
      title="📖 Manual de Uso do Playground RAG"
      description="Guia prático para testar consultas, avaliar relevância e otimizar collections no Qdrant."
      footer={
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-blue-700 cursor-pointer"
        >
          Entendi, fechar manual
        </button>
      }
    >
      <div className="space-y-6 text-sm text-slate-700 py-1">
        {/* Seção 1: O que é */}
        <section className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-100 text-blue-700 text-xs font-bold">
              1
            </span>
            <h4 className="font-bold text-slate-900">O que é o Playground?</h4>
          </div>
          <p className="text-xs leading-relaxed text-slate-600 pl-8">
            O <strong>Playground de Busca Semântica</strong> é um ambiente de testes e validação para o mecanismo RAG. Ele permite disparar a mesma pergunta em múltiplos perfis de coleção paralelamente para comparar a recuperação vetorial (k-NN) antes de disponibilizar documentos para o chatbot ou equipe de atendimento.
          </p>
        </section>

        {/* Seção 2: Passo a Passo */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 text-xs font-bold">
              2
            </span>
            <h4 className="font-bold text-slate-900">Passo a Passo de Uso</h4>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pl-8">
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 space-y-1">
              <span className="font-semibold text-xs text-slate-800">1. Pergunta de Teste</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Escreva perguntas reais no formato que usuários finais costumam enviar, incluindo sinônimos e termos específicos do domínio.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 space-y-1">
              <span className="font-semibold text-xs text-slate-800">2. Domínio de Negócio</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Filtre por <em>Vendas</em>, <em>Suporte Técnico</em> ou <em>Atendimento</em> para simular o comportamento de cada agente.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 space-y-1">
              <span className="font-semibold text-xs text-slate-800">3. Finalidade e Collections</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Escolha o <em>Purpose</em> (Chat, MCP B2B ou Admin) e marque duas ou mais coleções desse mesmo canal para um teste A/B legítimo.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 space-y-1">
              <span className="font-semibold text-xs text-slate-800">4. Executar Comparação</span>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Clique em <strong>Comparar</strong> para consultar o Qdrant e inspecionar os chunks lado a lado.
              </p>
            </div>
          </div>
        </section>

        {/* Seção 3: Como Interpretar as Métricas */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 text-xs font-bold">
              3
            </span>
            <h4 className="font-bold text-slate-900">Como Interpretar as Métricas</h4>
          </div>
          <div className="space-y-2.5 pl-8">
            <div className="rounded-xl border border-slate-200/80 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-800">🎯 Score de Similaridade (Cosseno)</span>
                <span className="text-[10px] text-slate-400 font-mono">0.000 a 1.000</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-emerald-50 border border-emerald-200/80 p-2 text-emerald-900">
                  <span className="font-bold block text-[11px]">≥ 0.80 Alta Relevância</span>
                  <span className="text-[10px] text-emerald-700 leading-tight block">Forte correlação semântica com a pergunta.</span>
                </div>
                <div className="rounded-lg bg-blue-50 border border-blue-200/80 p-2 text-blue-900">
                  <span className="font-bold block text-[11px]">0.60 – 0.79 Boa Relevância</span>
                  <span className="text-[10px] text-blue-700 leading-tight block">Contém contexto útil, pode ter termos periféricos.</span>
                </div>
                <div className="rounded-lg bg-amber-50 border border-amber-200/80 p-2 text-amber-900">
                  <span className="font-bold block text-[11px]">&lt; 0.60 Atenção / Ruído</span>
                  <span className="text-[10px] text-amber-700 leading-tight block">Pouca aderência. Avalie se o assunto está coberto.</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="rounded-xl border border-slate-200/80 p-3 space-y-1">
                <span className="text-xs font-semibold text-slate-800">⚡ Latência (ms)</span>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Tempo total para vetorização e consulta no Qdrant. Latências menores que 100ms são ideais para respostas fluidas no chat.
                </p>
              </div>
              <div className="rounded-xl border border-slate-200/80 p-3 space-y-1">
                <span className="text-xs font-semibold text-slate-800">📄 Granularidade do Chunk</span>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Verifique se o texto do chunk não foi interrompido no meio de instruções críticas. Se cortou, aumente o <code>chunk_size</code>.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Seção 4: Dicas Práticas */}
        <section className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100 text-amber-700 text-xs font-bold">
              4
            </span>
            <h4 className="font-bold text-slate-900">Dicas Práticas de Otimização</h4>
          </div>
          <ul className="list-disc list-inside text-xs text-slate-600 pl-8 space-y-1.5 leading-relaxed">
            <li><strong>Mesmo propósito (Purpose):</strong> compare apenas coleções com a mesma finalidade (ex: Chat vs Chat, MCP B2B vs MCP B2B). Misturar canais distintos distorce os scores e a relevância, pois cada um atende a regras de negócio e acervos documentais específicos.</li>
            <li><strong>Mantenha collections ativas:</strong> coleções ativas são as consumidas nos fluxos de produção.</li>
            <li><strong>Reingerir em nova collection:</strong> na aba de Ingestão de Documentos, você pode reingerir um mesmo arquivo em coleções diferentes para testá-las aqui.</li>
            <li><strong>Overlap adequado:</strong> para manuais técnicos de CFTV, um overlap de 100 a 150 tokens evita que conectores ou tabelas fiquem sem contexto.</li>
          </ul>
        </section>
      </div>
    </Modal>
  );
}

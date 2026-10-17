"use client";

interface Props {
  onSolicitarAtendente: () => void;
  onEncerrar: () => void;
  onLimparHistorico: () => void;
}

export function ChatActionsBar({ onSolicitarAtendente, onEncerrar, onLimparHistorico }: Props) {
  return (
    <div className="flex items-center justify-between gap-1.5 pt-1.5 border-t border-slate-100 text-xs">
      <div className="flex items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          onClick={onSolicitarAtendente}
          className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300/80 bg-emerald-50/90 px-2.5 py-1 text-[11px] sm:text-xs font-semibold text-emerald-800 shadow-2xs hover:bg-emerald-100 hover:border-emerald-400 transition-all active:scale-95 cursor-pointer"
          title="Solicitar transbordo para atendimento humano"
          aria-label="Falar com atendente humano"
        >
          <span>👤</span>
          <span>Falar com atendente</span>
        </button>
        <button
          type="button"
          onClick={onEncerrar}
          className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300/80 bg-amber-50/90 px-2.5 py-1 text-[11px] sm:text-xs font-semibold text-amber-800 shadow-2xs hover:bg-amber-100 hover:border-amber-400 transition-all active:scale-95 cursor-pointer"
          title="Encerrar atendimento atual e contabilizar métricas"
          aria-label="Encerrar atendimento"
        >
          <span>🏁</span>
          <span className="hidden xs:inline">Encerrar atendimento</span>
          <span className="xs:hidden">Encerrar</span>
        </button>
      </div>
      <button
        type="button"
        onClick={onLimparHistorico}
        className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200/80 bg-rose-50/90 px-2.5 py-1 text-[11px] sm:text-xs font-semibold text-rose-700 shadow-2xs hover:bg-rose-100 hover:border-rose-300 transition-all active:scale-95 cursor-pointer shrink-0"
        title="Apagar mensagens e memória da conversa"
        aria-label="Limpar histórico da conversa"
      >
        <span>🗑️</span>
        <span>Limpar histórico</span>
      </button>
    </div>
  );
}

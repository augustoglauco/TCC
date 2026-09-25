"use client";

import type { ChatEscalonamentoData } from "@/lib/types/chat";

export interface EscalonamentoBannerProps {
  escalonamento: ChatEscalonamentoData | null;
  onDismiss?: () => void;
}

export default function EscalonamentoBanner({
  escalonamento,
  onDismiss,
}: EscalonamentoBannerProps) {
  if (!escalonamento) return null;

  const { motivo } = escalonamento;

  let mensagem =
    "Sua conversa foi sinalizada para a nossa equipe humana para fornecer um suporte mais detalhado.";

  if (motivo === "urgencia") {
    mensagem =
      "Identificamos urgência na sua solicitação. Um atendente humano foi notificado e já está ciente do seu caso.";
  } else if (motivo === "insatisfacao") {
    mensagem =
      "Percebemos sua insatisfação e lamentamos o transtorno. Notificamos nossa equipe humana para acompanhar este atendimento prioritariamente.";
  }

  return (
    <div
      role="status"
      data-testid="escalonamento-banner"
      className="mb-2 sm:mb-3 rounded-xl border border-amber-300 bg-amber-50/95 p-3 sm:p-3.5 text-xs text-amber-950 shadow-2xs transition-all"
    >
      <div className="flex items-start justify-between gap-2.5">
        <div className="flex items-start gap-2.5">
          <span className="text-lg leading-none shrink-0" aria-hidden="true">
            🧑‍💼
          </span>
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-amber-900 text-xs sm:text-[13px]">
                Atendimento Humano Prioritário
              </span>
              <span className="inline-flex items-center rounded-full bg-amber-200/80 px-2 py-0.5 text-[10px] font-medium text-amber-900">
                Alerta de Tom
              </span>
            </div>
            <p className="text-amber-800 text-[11px] sm:text-xs leading-relaxed">
              {mensagem}
            </p>
          </div>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Fechar aviso de atendimento humano"
            className="rounded-lg p-1 text-amber-700 hover:bg-amber-100 hover:text-amber-900 transition-colors shrink-0 font-bold"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

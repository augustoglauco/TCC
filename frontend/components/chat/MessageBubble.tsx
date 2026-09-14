import type { ChatUIMessage } from "@/lib/types/chat";

// MVP: rótulo de domínio é só um mapa fixo de texto — sem i18n nem vindo do
// backend (ver docs/FRONTEND.md §3, "Indicador de domínio").
const DOMAIN_LABELS: Record<string, string> = {
  vendas: "Vendas",
  suporte: "Suporte Técnico",
  atendimento: "Atendimento ao Usuário",
  agendamento: "Agendamento",
  fora_escopo: "Fora de escopo",
};

interface MessageBubbleProps {
  message: ChatUIMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isExternalLlm = !isUser && message.backendUsed === "externo";
  const domainLabel = message.domain ? (DOMAIN_LABELS[message.domain] ?? message.domain) : null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        data-testid="message-bubble"
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : isExternalLlm
              ? "bg-blue-50 text-blue-900 ring-1 ring-inset ring-blue-200"
              : "bg-gray-100 text-gray-900"
        }`}
      >
        {!isUser && domainLabel && (
          <span
            data-testid="message-domain-label"
            className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-gray-500"
          >
            {domainLabel}
          </span>
        )}
        <p>{message.text}</p>
      </div>
    </div>
  );
}

interface ChatErroAlertaProps {
  texto: string;
  onRetry: () => void;
}

/** Alerta de erro de envio, com o botão "Tentar novamente" (R3). */
export function ChatErroAlerta({ texto, onRetry }: ChatErroAlertaProps) {
  return (
    <div
      role="alert"
      data-testid="chat-error"
      className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 shadow-2xs"
    >
      <p className="font-semibold">{texto}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-1 font-bold underline hover:no-underline"
      >
        Tentar novamente
      </button>
    </div>
  );
}

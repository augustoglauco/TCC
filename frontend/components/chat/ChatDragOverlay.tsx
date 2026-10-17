"use client";

interface ChatDragOverlayProps {
  visible: boolean;
}

export function ChatDragOverlay({ visible }: ChatDragOverlayProps) {
  if (!visible) return null;
  return (
    <div
      data-testid="chat-drag-overlay"
      className="absolute inset-0 z-50 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-blue-500 bg-blue-50/95 p-6 text-center backdrop-blur-xs transition-all"
    >
      <div className="rounded-full bg-blue-100 p-4 text-3xl shadow-xs">📥</div>
      <p className="mt-3 text-sm font-semibold text-blue-900">
        Solte a imagem ou áudio aqui para enviar
      </p>
      <p className="mt-1 text-xs text-blue-600">
        Suporta imagens (PNG, JPG, WEBP) e arquivos de áudio (MP3, WAV, M4A, etc.)
      </p>
    </div>
  );
}

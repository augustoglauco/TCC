"use client";

import React from "react";
import AudioRecorder from "@/components/chat/AudioRecorder";
import { ChatActionsBar } from "@/components/chat/ChatActionsBar";
import ImageUploader from "@/components/chat/ImageUploader";

interface ChatInputAreaProps {
  input: string;
  pendingImage: { base64: string; name: string } | null;
  controlsDisabled: boolean;
  isSending: boolean;
  canSend: boolean;
  showActions: boolean;
  onInputChange: (v: string) => void;
  onRemovePendingImage: () => void;
  onSubmit: (e: React.FormEvent) => void;
  onImageSelected: (base64: string, name: string) => void;
  onRecordingComplete: (audioBase64: string) => void;
  onRecordingStateChange: (recording: boolean) => void;
  onSolicitarAtendente: () => void;
  onEncerrar: () => void;
  onLimparHistorico: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}

export function ChatInputArea({
  input,
  pendingImage,
  controlsDisabled,
  isSending,
  canSend,
  showActions,
  onInputChange,
  onRemovePendingImage,
  onSubmit,
  onImageSelected,
  onRecordingComplete,
  onRecordingStateChange,
  onSolicitarAtendente,
  onEncerrar,
  onLimparHistorico,
  inputRef,
}: ChatInputAreaProps) {
  return (
    <div className="border-t border-slate-200/80 bg-white p-2 sm:p-3 rounded-b-xl shrink-0 flex flex-col gap-2">
      <form onSubmit={onSubmit} className="flex items-center gap-1.5 sm:gap-2 min-w-0">
        <label htmlFor="chat-modal-input" className="sr-only">
          Mensagem
        </label>
        {pendingImage && (
          <div className="flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700 max-w-[120px] sm:max-w-none truncate">
            <span className="truncate">🖼️ {pendingImage.name}</span>
            <button
              type="button"
              onClick={onRemovePendingImage}
              className="ml-1 font-bold hover:text-blue-900 shrink-0"
              aria-label="Remover imagem"
            >
              ×
            </button>
          </div>
        )}
        <input
          ref={inputRef}
          id="chat-modal-input"
          type="text"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          disabled={controlsDisabled}
          placeholder="Digite sua mensagem..."
          className="flex-1 min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-400/20 disabled:opacity-50"
        />
        <ImageUploader disabled={controlsDisabled} onImageSelected={onImageSelected} />
        <AudioRecorder
          disabled={isSending}
          onRecordingComplete={onRecordingComplete}
          onRecordingStateChange={onRecordingStateChange}
        />
        <button
          type="submit"
          disabled={!canSend}
          className="rounded-xl bg-slate-900 px-3.5 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-all active:scale-95 shadow-2xs shrink-0 cursor-pointer"
        >
          Enviar
        </button>
      </form>

      {showActions && (
        <ChatActionsBar
          onSolicitarAtendente={onSolicitarAtendente}
          onEncerrar={onEncerrar}
          onLimparHistorico={onLimparHistorico}
        />
      )}
    </div>
  );
}

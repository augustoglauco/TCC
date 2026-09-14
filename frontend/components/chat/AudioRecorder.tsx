"use client";

import { useRef, useState } from "react";

interface AudioRecorderProps {
  /** Desabilita o início de uma nova gravação (ex.: enquanto envia outra mensagem). */
  disabled?: boolean;
  /** Chamado com o áudio gravado, em base64, assim que a gravação é finalizada. */
  onRecordingComplete: (audioBase64: string) => void;
  /** Notifica o painel de chat para desabilitar outros controles durante a gravação. */
  onRecordingStateChange?: (isRecording: boolean) => void;
}

/** Converte um `Blob` de áudio em uma string base64 (sem o prefixo `data:...;base64,`). */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Falha ao ler o áudio gravado."));
        return;
      }
      const base64 = result.split(",")[1] ?? "";
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Falha ao ler o áudio gravado."));
    reader.readAsDataURL(blob);
  });
}

/**
 * Botão de microfone com comportamento de toggle (clique inicia a gravação,
 * clique de novo para e dispara `onRecordingComplete` automaticamente) — ver
 * `docs/FRONTEND.md` §3.
 *
 * # MVP: sem push-to-talk, sem VAD (detecção de fim de fala) e sem limite de
 * duração — a gravação só termina quando o usuário clica de novo (ver
 * docs/ARCHITECTURE.md §5/§7).
 */
export default function AudioRecorder({
  disabled,
  onRecordingComplete,
  onRecordingStateChange,
}: AudioRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const isSupported =
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined";

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        blobToBase64(blob)
          .then((base64) => onRecordingComplete(base64))
          .catch(() => setError("Não foi possível processar o áudio gravado. Tente novamente."));
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      onRecordingStateChange?.(true);
    } catch {
      setError("Não foi possível acessar o microfone. Verifique a permissão do navegador.");
      setIsRecording(false);
      onRecordingStateChange?.(false);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setIsRecording(false);
    onRecordingStateChange?.(false);
  }

  function handleClick() {
    if (isRecording) {
      stopRecording();
    } else {
      void startRecording();
    }
  }

  if (!isSupported) {
    return (
      <button
        type="button"
        disabled
        title="Gravação de áudio não é suportada neste navegador."
        aria-label="Gravação de áudio não suportada neste navegador"
        className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-400"
      >
        🎤
      </button>
    );
  }

  return (
    <div className="flex flex-col items-end">
      <button
        type="button"
        onClick={handleClick}
        disabled={!isRecording && disabled}
        aria-pressed={isRecording}
        aria-label={isRecording ? "Parar gravação" : "Gravar áudio"}
        data-testid="audio-recorder-button"
        className={`rounded px-3 py-2 text-sm font-medium transition-colors ${
          isRecording
            ? "animate-pulse bg-red-600 text-white"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        } disabled:opacity-50`}
      >
        {isRecording ? "⏹" : "🎤"}
      </button>
      {error && (
        <p role="alert" data-testid="audio-recorder-error" className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

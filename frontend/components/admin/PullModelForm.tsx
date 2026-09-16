"use client";

import { useEffect, useRef, useState } from "react";

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";
import type { PullStatusResponse } from "@/lib/types/localModels";

const POLL_INTERVAL_MS = 1000;

// Nº de falhas consecutivas de polling (ex.: instabilidade de rede, reinício
// momentâneo do backend) toleradas antes de tratar como erro fatal. O
// download em si continua rodando no servidor independentemente do polling.
const MAX_FALHAS_CONSECUTIVAS = 3;

const STORAGE_KEY = "gerenciador-modelos-locais:pull-em-andamento";

function lerNomeEmAndamento(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function salvarNomeEmAndamento(nome: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, nome);
  } catch {
    // localStorage indisponível (ex.: navegação privada) — o download em
    // si não é afetado, só a retomada automática após reload.
  }
}

function limparNomeEmAndamento(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ver salvarNomeEmAndamento
  }
}

export interface PullModelFormProps {
  onPulled: () => void;
}

export function PullModelForm({ onPulled }: PullModelFormProps) {
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState<PullStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const falhasConsecutivasRef = useRef(0);
  // Marca se uma submissão manual (handleSubmit) já começou — usado para o
  // efeito de retomada (abaixo) não pisar num submit manual concorrente.
  const submissaoManualIniciadaRef = useRef(false);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Retoma um download em andamento após remount/reload — o backend não
  // tem noção de "quem está observando", ele só mantém
  // `progress_store[name]` atualizado independentemente. Se havia um nome
  // salvo e o download ainda está `pulling`, reconecta o polling nele; caso
  // contrário (já terminou ou nunca existiu), limpa o nome salvo.
  useEffect(() => {
    let cancelado = false;

    async function retomarSeNecessario() {
      const nomeSalvo = lerNomeEmAndamento();
      if (!nomeSalvo) return;

      try {
        const status = await getPullStatus(nomeSalvo);
        // Uma submissão manual pode ter começado enquanto aguardávamos essa
        // resposta (ex.: o usuário submeteu outro modelo antes desta
        // retomada resolver) — nesse caso o submit manual já é dono do
        // polling/localStorage atuais, então a retomada não deve mais
        // aplicar seu resultado (evita derrubar o interval do submit manual
        // e sobrescrever o nome salvo dele).
        if (cancelado || submissaoManualIniciadaRef.current) return;
        if (status.status === "pulling") {
          setNome(nomeSalvo);
          setEnviando(true);
          setProgresso(status);
          iniciarPolling(nomeSalvo);
        } else {
          limparNomeEmAndamento();
        }
      } catch {
        if (!cancelado && !submissaoManualIniciadaRef.current) limparNomeEmAndamento();
      }
    }

    retomarSeNecessario();

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pararPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function iniciarPolling(nomeModelo: string) {
    pararPolling(); // garante que nunca há dois intervals concorrentes (ex.: retomada + submit numa corrida)
    falhasConsecutivasRef.current = 0;
    intervalRef.current = setInterval(async () => {
      try {
        const status = await getPullStatus(nomeModelo);
        falhasConsecutivasRef.current = 0;
        setProgresso(status);
        if (status.status === "done") {
          pararPolling();
          setEnviando(false);
          limparNomeEmAndamento();
          onPulled();
        } else if (status.status === "error") {
          // Erro definitivo reportado pelo próprio backend (o pull falhou de
          // verdade) — não é uma falha de polling, então para imediatamente.
          pararPolling();
          setEnviando(false);
          limparNomeEmAndamento();
          setError(status.detail ?? "Erro ao baixar o modelo.");
        }
      } catch (err) {
        falhasConsecutivasRef.current += 1;
        // Tolera falhas transitórias isoladas de polling (ex.: instabilidade
        // de rede de 1-2s, reinício momentâneo do backend) sem interromper o
        // download em andamento no servidor — só desiste após N falhas
        // consecutivas.
        if (falhasConsecutivasRef.current < MAX_FALHAS_CONSECUTIVAS) return;
        pararPolling();
        setEnviando(false);
        limparNomeEmAndamento();
        setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao consultar o progresso.");
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nome.trim() || enviando) return;

    submissaoManualIniciadaRef.current = true;
    setEnviando(true);
    setError(null);
    setProgresso(null);

    try {
      await pullModel(nome);
      salvarNomeEmAndamento(nome);
      iniciarPolling(nome);
    } catch (err) {
      setEnviando(false);
      setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao iniciar o download.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="pull-model-name" className="block text-sm font-medium text-gray-900">
          Nome do modelo
        </label>
        <input
          id="pull-model-name"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="ex.: llama3.1:8b ou hf.co/usuario/repo"
          disabled={enviando}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <button
        type="submit"
        disabled={!nome.trim() || enviando}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {enviando ? "Baixando..." : "Baixar"}
      </button>

      {progresso && progresso.status === "pulling" && (
        <div className="text-sm text-gray-600">
          {progresso.percent !== null && (
            <div className="mt-1 h-2 w-full rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-gray-900"
                style={{ width: `${Math.min(100, Math.max(0, progresso.percent))}%` }}
              />
            </div>
          )}
          <p className="mt-1">
            {progresso.percent !== null ? `${progresso.percent.toFixed(0)}% — ` : ""}
            {progresso.detail}
          </p>
        </div>
      )}
      {progresso && progresso.status === "done" && (
        <p className="rounded-md bg-green-50 px-4 py-3 text-green-800">{progresso.detail ?? "Concluído."}</p>
      )}
      {error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </form>
  );
}

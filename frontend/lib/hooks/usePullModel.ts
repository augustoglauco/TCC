"use client";

import { useEffect, useRef, useState } from "react";

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
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

function mensagemDeErro(err: unknown, padrao: string): string {
  return err instanceof LocalModelsApiError ? err.message : padrao;
}

// Estado e ações do download de um modelo local: submissão, polling do
// progresso e retomada automática após remount/reload.
export function usePullModel(onPulled: () => void) {
  const token = useAuthStore((s) => s.token);
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState<PullStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const falhasConsecutivasRef = useRef(0);
  // Marca se uma submissão manual (submit) já começou — usado para o
  // efeito de retomada (abaixo) não pisar num submit manual concorrente.
  const submissaoManualIniciadaRef = useRef(false);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function pararPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  // Fim do download (sucesso ou erro): para o polling e libera o formulário.
  function encerrarPull() {
    pararPolling();
    setEnviando(false);
    limparNomeEmAndamento();
  }

  function aplicarStatus(status: PullStatusResponse) {
    setProgresso(status);
    if (status.status === "done") {
      encerrarPull();
      onPulled();
    } else if (status.status === "error") {
      // Erro definitivo reportado pelo próprio backend (o pull falhou de
      // verdade) — não é uma falha de polling, então para imediatamente.
      encerrarPull();
      setError(status.detail ?? "Erro ao baixar o modelo.");
    }
  }

  function tratarFalhaDePolling(err: unknown) {
    falhasConsecutivasRef.current += 1;
    // Tolera falhas transitórias isoladas de polling (ex.: instabilidade
    // de rede de 1-2s, reinício momentâneo do backend) sem interromper o
    // download em andamento no servidor — só desiste após N falhas
    // consecutivas.
    if (falhasConsecutivasRef.current < MAX_FALHAS_CONSECUTIVAS) return;
    encerrarPull();
    setError(mensagemDeErro(err, "Erro inesperado ao consultar o progresso."));
  }

  function iniciarPolling(nomeModelo: string) {
    pararPolling(); // garante que nunca há dois intervals concorrentes (ex.: retomada + submit numa corrida)
    falhasConsecutivasRef.current = 0;
    intervalRef.current = setInterval(async () => {
      if (!token) return;
      try {
        const status = await getPullStatus(token, nomeModelo);
        falhasConsecutivasRef.current = 0;
        aplicarStatus(status);
      } catch (err) {
        tratarFalhaDePolling(err);
      }
    }, POLL_INTERVAL_MS);
  }

  // Retoma um download em andamento após remount/reload — o backend não
  // tem noção de "quem está observando", ele só mantém
  // `progress_store[name]` atualizado independentemente. Se havia um nome
  // salvo e o download ainda está `pulling`, reconecta o polling nele; caso
  // contrário (já terminou ou nunca existiu), limpa o nome salvo.
  useEffect(() => {
    let cancelado = false;
    // Uma submissão manual pode ter começado enquanto aguardávamos a resposta
    // (ex.: o usuário submeteu outro modelo antes desta retomada resolver) —
    // nesse caso o submit manual já é dono do polling/localStorage atuais, e
    // a retomada não deve aplicar seu resultado (evita derrubar o interval do
    // submit manual e sobrescrever o nome salvo dele).
    const obsoleta = () => cancelado || submissaoManualIniciadaRef.current;

    async function retomarSeNecessario() {
      const nomeSalvo = lerNomeEmAndamento();
      if (!nomeSalvo || !token) return;

      try {
        const status = await getPullStatus(token, nomeSalvo);
        if (obsoleta()) return;
        if (status.status !== "pulling") {
          limparNomeEmAndamento();
          return;
        }
        setNome(nomeSalvo);
        setEnviando(true);
        setProgresso(status);
        iniciarPolling(nomeSalvo);
      } catch {
        if (!obsoleta()) limparNomeEmAndamento();
      }
    }

    retomarSeNecessario();

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nome.trim() || enviando || !token) return;

    submissaoManualIniciadaRef.current = true;
    setEnviando(true);
    setError(null);
    setProgresso(null);

    try {
      await pullModel(token, nome);
      salvarNomeEmAndamento(nome);
      iniciarPolling(nome);
    } catch (err) {
      setEnviando(false);
      setError(mensagemDeErro(err, "Erro inesperado ao iniciar o download."));
    }
  }

  return { nome, setNome, enviando, progresso, error, submit };
}

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchMensagens,
  marcarMensagemLida,
  marcarTodasLidas,
  MensagemAgente,
} from "@/lib/api/mensagens";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

const ROTULO_AGENTE: Record<string, string> = {
  estoque_preditivo: "Agente de Estoque",
};

const ROTULO_EMAIL: Record<string, string> = {
  enviado: "E-mail enviado",
  nao_configurado: "E-mail não configurado",
  falhou: "Falha no e-mail",
  nao_enviado: "E-mail não enviado",
};

export default function AdminMensagensPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [mensagens, setMensagens] = useState<MensagemAgente[]>([]);
  const [naoLidas, setNaoLidas] = useState(0);
  const [apenasNaoLidas, setApenasNaoLidas] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchMensagens(token, apenasNaoLidas);
      setMensagens(res.mensagens);
      setNaoLidas(res.nao_lidas);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao consultar as mensagens.");
    } finally {
      setLoading(false);
    }
  }, [token, apenasNaoLidas]);

  useEffect(() => {
    if (isCurrentAdmin && token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregar();
    }
  }, [isCurrentAdmin, token, carregar]);

  const acao = async (fn: () => Promise<void>) => {
    try {
      await fn();
      await carregar();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar a mensagem.");
    }
  };

  if (!currentUser || !isCurrentAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <h1 className="text-xl font-semibold text-gray-900">Acesso restrito</h1>
        <p className="mt-2 text-sm text-gray-600">Esta página é exclusiva de administradores.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Mensagens de Agentes</h1>
          <p className="mt-1 text-sm text-gray-600">
            Avisos enviados pelos agentes autônomos ao administrador.{" "}
            <span data-testid="nao-lidas">{naoLidas} não lida(s)</span>.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={apenasNaoLidas}
              onChange={(e) => setApenasNaoLidas(e.target.checked)}
            />
            Só não lidas
          </label>
          <button
            type="button"
            onClick={() => void acao(() => marcarTodasLidas(token!))}
            disabled={naoLidas === 0}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Marcar todas como lidas
          </button>
          <button
            type="button"
            onClick={() => void carregar()}
            disabled={loading}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {loading ? "Atualizando..." : "Atualizar"}
          </button>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
        >
          {error}
        </div>
      )}

      {mensagens.length === 0 && !loading && (
        <p className="rounded-xl border border-gray-200 bg-white px-4 py-10 text-center text-sm text-gray-600">
          Nenhuma mensagem de agentes.
        </p>
      )}

      <ul className="space-y-3">
        {mensagens.map((m) => (
          <li
            key={m.id}
            className={
              m.lida
                ? "rounded-xl border border-gray-200 bg-white p-4"
                : "rounded-xl border-2 border-blue-300 bg-blue-50/40 p-4"
            }
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={
                    m.severidade === "critico"
                      ? "rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-medium text-rose-700"
                      : "rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700"
                  }
                >
                  {m.severidade === "critico" ? "Crítico" : "Aviso"}
                </span>
                <span className="text-xs font-medium text-gray-500">
                  {ROTULO_AGENTE[m.agente] ?? m.agente}
                </span>
              </div>
              <span className="text-xs text-gray-400">
                {m.criado_em ? new Date(m.criado_em).toLocaleString("pt-BR") : ""}
              </span>
            </div>
            <h2 className="mt-2 font-semibold text-gray-900">{m.titulo}</h2>
            <p className="mt-1 text-sm text-gray-700">{m.corpo}</p>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-gray-500">
                {ROTULO_EMAIL[m.email_status] ?? m.email_status}
              </span>
              {!m.lida && (
                <button
                  type="button"
                  onClick={() => void acao(() => marcarMensagemLida(token!, m.id))}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Marcar como lida
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

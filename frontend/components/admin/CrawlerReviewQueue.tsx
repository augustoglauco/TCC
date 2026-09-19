"use client";

import { useCallback, useEffect, useState } from "react";

import { ToastStack, useToast } from "@/components/ui/Toast";
import { CrawlerApiError, approvePendingPage, listPendingPages, rejectPendingPage } from "@/lib/api/crawler";
import type { PendingPage } from "@/lib/types/crawler";
import type { RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

export function CrawlerReviewQueue({ reloadKey }: { reloadKey: number }) {
  const [pages, setPages] = useState<PendingPage[] | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<Record<string, RagDomain>>({});
  const [processingId, setProcessingId] = useState<string | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregar = useCallback(async () => {
    try {
      const carregadas = await listPendingPages();
      setPages(carregadas);
      setSelectedDomain((atual) => {
        const proximo = { ...atual };
        for (const page of carregadas) {
          proximo[page.id] = proximo[page.id] ?? page.domain_proposed;
        }
        return proximo;
      });
    } catch (err) {
      showToast(
        err instanceof CrawlerApiError ? err.message : "Erro inesperado ao carregar a fila de revisão.",
        "error",
      );
      setPages([]);
    }
  }, [showToast]);

  useEffect(() => {
    // `carregar` só chama `setPages`/`showToast` depois do `await`
    // (assíncrono, não durante a execução síncrona do efeito) — falso
    // positivo conhecido de `react-hooks/set-state-in-effect`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar();
  }, [carregar, reloadKey]);

  async function handleApprove(page: PendingPage) {
    setProcessingId(page.id);
    try {
      await approvePendingPage(page.id, { domain: selectedDomain[page.id] ?? page.domain_proposed });
      showToast(`"${page.url}" aprovada e ingerida.`, "success");
      setPages((atual) => atual?.filter((p) => p.id !== page.id) ?? null);
    } catch (err) {
      showToast(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao aprovar.", "error");
    } finally {
      setProcessingId(null);
    }
  }

  async function handleReject(page: PendingPage) {
    setProcessingId(page.id);
    try {
      await rejectPendingPage(page.id);
      showToast(`"${page.url}" rejeitada.`, "success");
      setPages((atual) => atual?.filter((p) => p.id !== page.id) ?? null);
    } catch (err) {
      showToast(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao rejeitar.", "error");
    } finally {
      setProcessingId(null);
    }
  }

  if (pages === null) {
    return <p className="text-sm text-gray-600">Carregando...</p>;
  }

  if (pages.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma página pendente de revisão.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
      <table className="w-full min-w-[700px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
            <th className="py-3 px-4">URL</th>
            <th className="py-3 px-4">Trecho</th>
            <th className="py-3 px-4">Domínio</th>
            <th className="py-3 px-4">Confiança</th>
            <th className="py-3 px-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {pages.map((page) => (
            <tr key={page.id} className="transition-colors hover:bg-slate-50/60">
              <td className="py-3.5 px-4 font-semibold text-slate-900 break-all">{page.url}</td>
              <td className="py-3.5 px-4 text-slate-600 text-xs">{page.text_snippet}</td>
              <td className="py-3.5 px-4">
                <select
                  value={selectedDomain[page.id] ?? page.domain_proposed}
                  onChange={(event) =>
                    setSelectedDomain((atual) => ({
                      ...atual,
                      [page.id]: event.target.value as RagDomain,
                    }))
                  }
                  className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-900"
                >
                  {DOMAIN_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </td>
              <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">
                {page.confidence.toFixed(2)}
              </td>
              <td className="py-3.5 px-4 text-right whitespace-nowrap">
                <button
                  type="button"
                  disabled={processingId === page.id}
                  onClick={() => handleApprove(page)}
                  className="mr-2 inline-flex items-center gap-1 rounded-lg border border-green-200/80 bg-green-50/50 px-2.5 py-1 text-xs font-semibold text-green-700 shadow-2xs transition-colors hover:bg-green-100/80 hover:text-green-800 disabled:opacity-50"
                >
                  Aprovar
                </button>
                <button
                  type="button"
                  disabled={processingId === page.id}
                  onClick={() => handleReject(page)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-200/80 bg-red-50/50 px-2.5 py-1 text-xs font-semibold text-red-600 shadow-2xs transition-colors hover:bg-red-100/80 hover:text-red-700 disabled:opacity-50"
                >
                  Rejeitar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

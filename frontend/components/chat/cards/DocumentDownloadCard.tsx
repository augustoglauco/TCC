import type { ChatCardDocumentoDownload } from "@/lib/types/chat";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

/** Formata bytes em KB/MB para exibição no card (sem utilitário existente
 * no repo para isso — helper local simples, só o suficiente para o MVP). */
function formatarTamanhoArquivo(bytes?: number | null): string | null {
  if (bytes == null) return null;
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

/** Card rico de download de documento-fonte do RAG (Fase 8) — emitido pelo
 * backend no evento `done` quando a confiança do RAG é suficiente. O
 * backend só emite este card para documentos cuja coleção de origem tem
 * `purpose="chat"`, então o endpoint de download (`GET
 * /api/rag/documents/{id}/download`) é sempre público e não exige token
 * aqui no frontend. */
export default function DocumentDownloadCard({ card }: { card: ChatCardDocumentoDownload }) {
  const relevancia = Math.round(card.score * 100);
  const tamanho = formatarTamanhoArquivo(card.file_size_bytes);
  const downloadUrl = `${getApiBaseUrl()}${card.download_url}`;

  return (
    <div className="flex w-full max-w-[85%] gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xs">
      <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100">
        <span className="text-2xl">📄</span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        <p className="truncate text-sm font-semibold text-slate-900">{card.filename}</p>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-fit rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
            Relevância {relevancia}%
          </span>
          {tamanho ? <span className="text-[11px] text-slate-500">{tamanho}</span> : null}
        </div>
        <a
          href={downloadUrl}
          download={card.filename}
          className="mt-1 w-fit rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
        >
          📥 Baixar Documento
        </a>
      </div>
    </div>
  );
}

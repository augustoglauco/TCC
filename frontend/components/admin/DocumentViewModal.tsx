"use client";

import { useEffect, useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { fetchDocumentContent, getDocumentContentUrl } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

export interface DocumentViewModalProps {
  documento: DocumentRegistryEntry | null;
  onOpenChange: (open: boolean) => void;
}

type FileType = "pdf" | "csv" | "md" | "txt" | "other";

function detectarTipoArquivo(filename: string): FileType {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "pdf";
  if (lower.endsWith(".csv")) return "csv";
  if (lower.endsWith(".md")) return "md";
  if (lower.endsWith(".txt")) return "txt";
  return "other";
}

function parseLinhaCSV(line: string, delimiter: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === delimiter && !inQuotes) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}

function parseCSV(text: string): { headers: string[]; rows: string[][] } {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  if (lines.length === 0) return { headers: [], rows: [] };

  // Detecta ; vs , pelo cabeçalho — campos sem aspas podem conter espaço
  // (ex.: "Gerador GD-30"), então o corte é só no delimitador escolhido,
  // nunca em espaço em branco.
  const delimiter = lines[0].includes(";") ? ";" : ",";
  const rows = lines.map((line) => parseLinhaCSV(line, delimiter));

  return {
    headers: rows[0] || [],
    rows: rows.slice(1),
  };
}

export function DocumentViewModal({ documento, onOpenChange }: DocumentViewModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [documentoCarregadoId, setDocumentoCarregadoId] = useState<string | null>(null);

  const fileType = documento ? detectarTipoArquivo(documento.filename) : "other";

  // Reseta o estado de exibição durante a renderização (não num efeito)
  // quando o documento muda — padrão recomendado pelo React para "ajustar
  // estado quando uma prop muda" (evita o commit extra/cascata de um reset
  // feito de dentro de um useEffect).
  if ((documento?.id ?? null) !== documentoCarregadoId) {
    setDocumentoCarregadoId(documento?.id ?? null);
    setLoading(documento !== null);
    setError(null);
    setContent(null);
    setBlobUrl(null);
  }

  useEffect(() => {
    if (!documento) {
      return;
    }

    // `urlCriada` (não o state `blobUrl`) é o que a limpeza abaixo revoga —
    // roda tanto ao trocar de documento quanto ao desmontar, então nunca
    // vaza um object URL, mesmo indo direto de um PDF para outro.
    let active = true;
    let urlCriada: string | null = null;

    fetchDocumentContent(documento.id)
      .then(({ blob, text }) => {
        if (!active) return;
        if (fileType === "pdf") {
          urlCriada = URL.createObjectURL(blob);
          setBlobUrl(urlCriada);
        } else if (text !== undefined) {
          setContent(text);
        } else {
          blob.text().then((txt) => {
            if (active) setContent(txt);
          });
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Erro ao carregar conteúdo do documento.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      if (urlCriada) URL.revokeObjectURL(urlCriada);
    };
  }, [documento, fileType]);

  if (!documento) return null;

  const downloadUrl = getDocumentContentUrl(documento.id);

  return (
    <Modal
      open={documento !== null}
      onOpenChange={onOpenChange}
      title={`Visualizar: ${documento.filename}`}
      description={`Domínio: ${documento.domain} • ${documento.chunk_count} chunk(s) • Collection: ${
        documento.collection_name || "N/A"
      }`}
      size="3xl"
      footer={
        <div className="flex w-full items-center justify-between">
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            download={documento.filename}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:text-blue-600 transition-colors"
          >
            📥 Baixar original
          </a>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition-colors"
          >
            Fechar
          </button>
        </div>
      }
    >
      {loading && (
        <div className="flex h-64 items-center justify-center gap-2 text-sm text-slate-500">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          <span>Carregando documento...</span>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50/60 p-4 text-sm text-red-700">
          <p className="font-semibold">Não foi possível carregar o arquivo:</p>
          <p className="mt-1 text-xs">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="mt-1">
          {fileType === "pdf" && blobUrl && (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-inner">
              <iframe
                src={blobUrl}
                title={documento.filename}
                className="h-[62vh] w-full border-0"
              />
            </div>
          )}

          {fileType === "csv" && content !== null && (
            <div className="max-h-[62vh] overflow-auto rounded-xl border border-slate-200/90 bg-white shadow-xs">
              {(() => {
                const { headers, rows } = parseCSV(content);
                if (headers.length === 0) {
                  return <p className="p-4 text-xs text-slate-500">Arquivo CSV vazio.</p>;
                }
                return (
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 border-b border-slate-200 bg-slate-100 font-semibold text-slate-700 shadow-2xs">
                      <tr>
                        {headers.map((h, i) => (
                          <th key={i} className="px-3.5 py-2.5 whitespace-nowrap">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {rows.map((row, rowIndex) => (
                        <tr key={rowIndex} className="transition-colors hover:bg-slate-50">
                          {row.map((cell, cellIndex) => (
                            <td key={cellIndex} className="px-3.5 py-2 text-slate-800 font-mono">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
            </div>
          )}

          {(fileType === "md" || fileType === "txt" || fileType === "other") && content !== null && (
            <div className="max-h-[62vh] overflow-y-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-200 whitespace-pre-wrap shadow-inner selection:bg-blue-600 selection:text-white">
              {content}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

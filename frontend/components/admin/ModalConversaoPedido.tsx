"use client";

import React, { useState } from "react";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  analisarComprovante,
  confirmarConversaoManual,
  converterAutoAdmin,
  converterManualSimples,
  type AnaliseComprovanteResponse,
  type PedidoAdminItem,
} from "@/lib/api/adminPedidos";

interface ModalConversaoPedidoProps {
  pedido: PedidoAdminItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ModalConversaoPedido({
  pedido,
  isOpen,
  onClose,
  onSuccess,
}: ModalConversaoPedidoProps) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);

  const [modo, setModo] = useState<"simples" | "padrao" | "auto">("simples");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Estados Modo 1: Manual Simples
  const [operadorSimples, setOperadorSimples] = useState(user?.nome || "Admin");
  const [arquivoSimples, setArquivoSimples] = useState<File | null>(null);

  // Estados Modo 2: Manual com IA
  const [arquivoAnalise, setArquivoAnalise] = useState<File | null>(null);
  const [analiseResultado, setAnaliseResultado] = useState<AnaliseComprovanteResponse | null>(null);

  // Estados Modo 3: Auto
  const [arquivoAuto, setArquivoAuto] = useState<File | null>(null);

  if (!isOpen || !pedido) return null;

  async function handleConverterSimples() {
    if (!token) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await converterManualSimples(
        pedido!.id,
        {
          convertido_por: operadorSimples,
          comprovante: arquivoSimples || undefined,
        },
        token
      );
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao converter pedido");
    } finally {
      setLoading(false);
    }
  }

  async function handleAuditarIA() {
    if (!token || !arquivoAnalise) {
      setErrorMsg("Selecione um arquivo de comprovante para auditar com a IA.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await analisarComprovante(pedido!.id, arquivoAnalise, token);
      setAnaliseResultado(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao auditar comprovante");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmarComIA() {
    if (!token || !analiseResultado) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await confirmarConversaoManual(
        pedido!.id,
        {
          comprovante_url: analiseResultado.comprovante_url,
          parecer_json: JSON.stringify(analiseResultado.parecer),
          convertido_por: user?.nome || "Admin IA Conferido",
        },
        token
      );
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro ao confirmar conversão");
    } finally {
      setLoading(false);
    }
  }

  async function handleConverterAuto() {
    if (!token || !arquivoAuto) {
      setErrorMsg("Selecione um arquivo de comprovante.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      await converterAutoAdmin(pedido!.id, arquivoAuto, token);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Falha na conversão automática");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="relative w-full max-w-2xl rounded-xl bg-white p-6 shadow-2xl overflow-y-auto max-h-[90vh]">
        <div className="flex items-center justify-between border-b pb-3">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Modal de Conversão de Reserva</h3>
            <p className="text-xs text-gray-500">Reserva ID: {pedido.id}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        {/* Resumo da Reserva */}
        <div className="mt-4 rounded-lg bg-gray-50 p-3 text-sm flex flex-wrap gap-4 justify-between border border-gray-200">
          <div>
            <span className="text-gray-500 block text-xs">Cliente / Comprador</span>
            <span className="font-semibold text-gray-800">{pedido.user_email || "N/A"}</span>
          </div>
          <div>
            <span className="text-gray-500 block text-xs">Valor Total</span>
            <span className="font-bold text-emerald-700">
              R$ {pedido.valor_total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div>
            <span className="text-gray-500 block text-xs">Status Atual</span>
            <span
              className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                pedido.status === "venda_concluida"
                  ? "bg-green-100 text-green-800"
                  : pedido.status === "pagamento_divergente"
                  ? "bg-red-100 text-red-800"
                  : "bg-amber-100 text-amber-800"
              }`}
            >
              {pedido.status}
            </span>
          </div>
        </div>

        {/* Comprovante pré-existente ou parecer salvo */}
        {pedido.comprovante_url && (
          <div className="mt-3 text-xs text-blue-600 bg-blue-50 p-2.5 rounded border border-blue-200 flex items-center justify-between">
            <span>📎 Comprovante anexado no pedido:</span>
            <a
              href={pedido.comprovante_url}
              target="_blank"
              rel="noreferrer"
              className="underline font-semibold hover:text-blue-800"
            >
              Abrir Arquivo
            </a>
          </div>
        )}

        {pedido.llm_parecer && (
          <div className="mt-2 text-xs bg-gray-100 p-2.5 rounded border border-gray-300">
            <span className="font-semibold text-gray-700 block mb-1">Parecer da Auditoria:</span>
            <pre className="text-[11px] overflow-x-auto text-gray-600 font-mono whitespace-pre-wrap">
              {pedido.llm_parecer}
            </pre>
          </div>
        )}

        {errorMsg && (
          <div className="mt-3 rounded bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Seletor de Modalidade */}
        <div className="mt-5 border-b flex gap-2">
          <button
            type="button"
            onClick={() => setModo("simples")}
            className={`pb-2 px-3 text-sm font-medium border-b-2 transition-colors ${
              modo === "simples"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            1. Manual Simples
          </button>
          <button
            type="button"
            onClick={() => setModo("padrao")}
            className={`pb-2 px-3 text-sm font-medium border-b-2 transition-colors ${
              modo === "padrao"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            2. Manual com IA
          </button>
          <button
            type="button"
            onClick={() => setModo("auto")}
            className={`pb-2 px-3 text-sm font-medium border-b-2 transition-colors ${
              modo === "auto"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            3. Automática (IA)
          </button>
        </div>

        {/* Conteúdo da Modalidade Selecionada */}
        <div className="mt-4">
          {modo === "simples" && (
            <div className="space-y-4">
              <p className="text-xs text-gray-600">
                Converte a reserva em venda diretamente, sem validação automatizada de IA (para pagamentos já conferidos no banco ou via extrato).
              </p>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Operador Responsável:
                </label>
                <input
                  type="text"
                  value={operadorSimples}
                  onChange={(e) => setOperadorSimples(e.target.value)}
                  className="w-full rounded border border-gray-300 p-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Anexar Comprovante (opcional):
                </label>
                <input
                  type="file"
                  onChange={(e) => setArquivoSimples(e.target.files?.[0] || null)}
                  className="w-full text-xs text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
                />
              </div>
              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={handleConverterSimples}
                  className="rounded bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? "Convertendo..." : "Confirmar Conversão Simples"}
                </button>
              </div>
            </div>
          )}

          {modo === "padrao" && (
            <div className="space-y-4">
              <p className="text-xs text-gray-600">
                Auditoria com IA: O comprovante é processado pelo modelo de Visão/LLM e o parecer financeiro é apresentado para sua validação humana antes de concluir a venda.
              </p>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Selecionar Comprovante (PDF, Imagem):
                </label>
                <input
                  type="file"
                  data-testid="input-file-analise"
                  onChange={(e) => setArquivoAnalise(e.target.files?.[0] || null)}
                  className="w-full text-xs text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
                />
              </div>

              <button
                type="button"
                disabled={loading || !arquivoAnalise}
                onClick={handleAuditarIA}
                className="w-full rounded bg-indigo-600 py-2 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? "Auditando com IA..." : "🔍 Auditar com IA"}
              </button>

              {analiseResultado && (
                <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-xs space-y-1.5">
                  <div className="flex justify-between items-center font-semibold text-indigo-900">
                    <span>Resultado da Auditoria da IA:</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] ${
                        analiseResultado.parecer.valido
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {analiseResultado.parecer.valido ? "Válido" : "Divergente"}
                    </span>
                  </div>
                  <p className="text-gray-700">
                    <strong>Valor Detectado:</strong> R${" "}
                    {analiseResultado.parecer.valor_pago.toFixed(2)} |{" "}
                    <strong>Divergência:</strong> R${" "}
                    {analiseResultado.parecer.divergencia.toFixed(2)}
                  </p>
                  {analiseResultado.parecer.codigo_transacao && (
                    <p className="text-gray-700">
                      <strong>Código/Autenticação:</strong>{" "}
                      {analiseResultado.parecer.codigo_transacao}
                    </p>
                  )}
                  <p className="text-gray-700">
                    <strong>Justificativa:</strong> {analiseResultado.parecer.justificativa}
                  </p>

                  <div className="pt-2 flex justify-end gap-2">
                    <button
                      type="button"
                      disabled={loading}
                      onClick={handleConfirmarComIA}
                      className="rounded bg-green-600 px-4 py-2 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {loading ? "Aprovando..." : "✅ Aprovar e Concluir Venda"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {modo === "auto" && (
            <div className="space-y-4">
              <p className="text-xs text-gray-600">
                Conversão Automática via Upload: Se a IA validar o valor integral sem divergências, o status é alterado para <strong>venda_concluida</strong> imediatamente. Caso contrário, o pedido será marcado como <strong>pagamento_divergente</strong>.
              </p>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Comprovante para Validação Automática:
                </label>
                <input
                  type="file"
                  data-testid="input-file-auto"
                  onChange={(e) => setArquivoAuto(e.target.files?.[0] || null)}
                  className="w-full text-xs text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  disabled={loading || !arquivoAuto}
                  onClick={handleConverterAuto}
                  className="rounded bg-emerald-600 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {loading ? "Processando..." : "⚡ Validar e Converter Automaticamente via IA"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

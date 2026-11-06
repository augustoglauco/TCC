"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchStatusAgenteEstoque, type StatusAgenteEstoque } from "@/lib/api/estoqueAgente";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

type Estado = "ok" | "desativado" | "aguardando" | "erro" | "indisponivel";

const ESTILOS: Record<Estado, { caixa: string; bolinha: string }> = {
  ok: { caixa: "border-emerald-200 bg-emerald-50 text-emerald-900", bolinha: "bg-emerald-500" },
  desativado: { caixa: "border-gray-200 bg-gray-50 text-gray-700", bolinha: "bg-gray-400" },
  aguardando: { caixa: "border-amber-200 bg-amber-50 text-amber-900", bolinha: "bg-amber-500" },
  erro: { caixa: "border-rose-200 bg-rose-50 text-rose-900", bolinha: "bg-rose-500" },
  indisponivel: { caixa: "border-gray-200 bg-gray-50 text-gray-700", bolinha: "bg-gray-400" },
};

function haQuanto(iso: string | null): string {
  if (!iso) return "—";
  const minutos = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60_000));
  if (minutos < 1) return "agora há pouco";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 48) return `há ${horas} h`;
  return `há ${Math.floor(horas / 24)} d`;
}

function nomeDoModo(status: StatusAgenteEstoque): string {
  if (status.modo !== "ia") return "determinístico";
  return status.llm === "externo" ? "IA externa" : "IA local";
}

function plural(n: number, singular: string, pluralForma: string): string {
  return `${n} ${n === 1 ? singular : pluralForma}`;
}

function estadoDe(status: StatusAgenteEstoque): Estado {
  if (status.modo === "desativado") return "desativado";
  if (!status.ultima_execucao) return "aguardando";
  return status.ultima_execucao.erro ? "erro" : "ok";
}

function descricao(status: StatusAgenteEstoque, estado: Estado): string {
  const modo = nomeDoModo(status);
  const execucao = status.ultima_execucao;
  if (estado === "desativado") return "Agente de estoque desativado";
  if (estado === "aguardando") {
    return `Agente de estoque ativo (${modo}) · aguardando o primeiro pedido`;
  }
  const quando = haQuanto(execucao?.criado_em ?? null);
  if (estado === "erro") {
    return `Agente de estoque ativo (${modo}) · última avaliação falhou ${quando}`;
  }
  const produtos = plural(
    execucao?.produtos_avaliados ?? 0,
    "produto avaliado",
    "produtos avaliados",
  );
  // "Novos": o agente não repete o alerta de um produto por 24 h, então uma rodada
  // seguinte ao alerta mostra 0 mesmo havendo alerta ativo em Mensagens de Agentes.
  const alertas = plural(execucao?.alertas_criados ?? 0, "alerta novo", "alertas novos");
  const ultimo = status.ultimo_alerta_em
    ? ` · último alerta ${haQuanto(status.ultimo_alerta_em)}`
    : "";
  return `Agente de estoque ativo (${modo}) · última avaliação ${quando} · ${produtos}, ${alertas}${ultimo}`;
}

/** Mostra no catálogo se o agente de estoque está habilitado e quando avaliou pela última vez. */
export function AgenteEstoqueIndicador() {
  const token = useAuthStore((s) => s.token);
  const [status, setStatus] = useState<StatusAgenteEstoque | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    if (!token) return;
    let ativo = true;
    fetchStatusAgenteEstoque(token)
      .then((s) => ativo && setStatus(s))
      .catch(() => ativo && setFalhou(true));
    return () => {
      ativo = false;
    };
  }, [token]);

  if (!status && !falhou) return null;

  const estado: Estado = status ? estadoDe(status) : "indisponivel";
  const texto = status ? descricao(status, estado) : "Agente de estoque: status indisponível";
  const motivo = status?.ultima_execucao?.erro ?? undefined;
  const estilo = ESTILOS[estado];

  return (
    <div
      data-testid="agente-estoque-indicador"
      data-estado={estado}
      title={motivo}
      className={`flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-xs sm:text-sm ${estilo.caixa}`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${estilo.bolinha}`} aria-hidden />
      <span>{texto}</span>
      {estado === "desativado" && (
        <Link href="/admin/modelos" className="font-semibold underline">
          Ativar em Modelos
        </Link>
      )}
    </div>
  );
}

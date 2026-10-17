"use client";

import type { ConjuntoStatus } from "@/lib/api/datasets";

/**
 * Cartões de progresso dos cinco conjuntos da Estratégia A
 * (`docs/EVALUATION.md` Seção 0). O cartão é o seletor da fila de revisão
 * ao lado; os de gabarito automático (imagem e banco) não têm fila e
 * aparecem como prontos.
 */
export function DatasetsConjuntoCards({
  conjuntos,
  selecionado,
  onSelecionar,
}: {
  conjuntos: ConjuntoStatus[];
  selecionado: string | null;
  onSelecionar: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {conjuntos.map((c) => (
        <CartaoConjunto
          key={c.id}
          conjunto={c}
          ativo={c.id === selecionado}
          onSelecionar={() => onSelecionar(c.id)}
        />
      ))}
    </div>
  );
}

function CartaoConjunto({
  conjunto,
  ativo,
  onSelecionar,
}: {
  conjunto: ConjuntoStatus;
  ativo: boolean;
  onSelecionar: () => void;
}) {
  const revisados = conjunto.aprovados + conjunto.corrigidos + conjunto.descartados;
  // Duas barras distintas: quanto do conjunto existe (total x meta) e quanto
  // do que existe já foi revisado. Um conjunto 100% revisado com 18 de 180
  // itens não está pronto, e uma barra só esconderia isso.
  const pctGerado = conjunto.meta > 0 ? Math.min(100, (conjunto.total / conjunto.meta) * 100) : 0;
  const pctRevisado = conjunto.total > 0 ? (revisados / conjunto.total) * 100 : 0;

  return (
    <button
      type="button"
      onClick={onSelecionar}
      aria-pressed={ativo}
      className={`rounded-lg border p-4 text-left transition ${
        ativo
          ? "border-emerald-400 bg-emerald-50/60 ring-2 ring-emerald-200"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900">{conjunto.nome}</h3>
        {conjunto.revisao_automatica ? (
          <span
            title="Gabarito exato por construção: não passa por revisão humana."
            className="shrink-0 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700"
          >
            automático
          </span>
        ) : null}
      </div>

      <p className="mt-2 text-2xl font-semibold tabular-nums text-gray-900">
        {conjunto.total}
        <span className="text-sm font-normal text-gray-500"> / {conjunto.meta}</span>
      </p>

      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
        <div className="h-full bg-gray-400" style={{ width: `${pctGerado}%` }} />
      </div>

      {!conjunto.existe ? (
        <p className="mt-2 text-xs text-amber-700">Ainda não gerado</p>
      ) : conjunto.revisao_automatica ? (
        <p className="mt-2 text-xs text-gray-500">Sem fila de revisão</p>
      ) : (
        <>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
            <div className="h-full bg-emerald-500" style={{ width: `${pctRevisado}%` }} />
          </div>
          <p className="mt-2 text-xs text-gray-600 tabular-nums">
            {conjunto.pendentes} pendente{conjunto.pendentes === 1 ? "" : "s"} · {revisados}{" "}
            revisado{revisados === 1 ? "" : "s"}
          </p>
          {conjunto.descartados > 0 ? (
            <p className="text-xs text-gray-500 tabular-nums">
              {conjunto.descartados} descartado{conjunto.descartados === 1 ? "" : "s"}
            </p>
          ) : null}
        </>
      )}
    </button>
  );
}

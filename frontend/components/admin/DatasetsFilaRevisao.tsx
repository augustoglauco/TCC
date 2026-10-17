"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchItens,
  revisarItem,
  type ConjuntoStatus,
  type ItemRevisao,
  type StatusRevisao,
} from "@/lib/api/datasets";

/**
 * Fila de revisão item a item de um conjunto.
 *
 * O desenho vem do orçamento de ~4,5 h da Estratégia A: um item por vez, os
 * campos já editáveis (corrigir é mais comum que descartar) e atalhos de
 * teclado, porque a meta é ~10 s por item do RAG de documentos — com o
 * trecho de origem ao lado, não caçado no PDF.
 */
export function DatasetsFilaRevisao({
  conjunto,
  token,
  onRevisado,
}: {
  conjunto: ConjuntoStatus;
  token: string;
  onRevisado: () => void;
}) {
  const [itens, setItens] = useState<ItemRevisao[] | null>(null);
  const [posicao, setPosicao] = useState(0);
  const [edicoes, setEdicoes] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const res = await fetchItens(conjunto.id, token, { apenasPendentes: true, limite: 20 });
      setItens(res.itens);
      setPosicao(0);
      setEdicoes({});
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Erro ao carregar a fila.");
    }
  }, [conjunto.id, token]);

  useEffect(() => {
    // Conjunto de gabarito automático não tem fila: o render devolve antes
    // de olhar `itens`, então não há o que carregar nem o que zerar.
    if (conjunto.revisao_automatica || !conjunto.existe) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregar();
  }, [carregar, conjunto.revisao_automatica, conjunto.existe]);

  const atual = itens?.[posicao] ?? null;

  const decidir = useCallback(
    async (status: StatusRevisao) => {
      if (!atual || salvando) return;
      setSalvando(true);
      setErro(null);
      try {
        // Só manda `campos` quando houve correção: o backend faz update, e
        // "aprovado" com o item intacto não deve reescrever nada.
        const campos = Object.keys(edicoes).length > 0 ? edicoes : undefined;
        await revisarItem(conjunto.id, atual.indice, campos ? "corrigido" : status, token, campos);
        setEdicoes({});
        setPosicao((p) => p + 1);
        onRevisado();
      } catch (err: unknown) {
        setErro(err instanceof Error ? err.message : "Erro ao gravar a revisão.");
      } finally {
        setSalvando(false);
      }
    },
    [atual, conjunto.id, edicoes, onRevisado, salvando, token],
  );

  // Atalhos: A aprova, D descarta. Ignorados enquanto o foco está num campo,
  // senão digitar uma correção dispararia a decisão.
  useEffect(() => {
    function aoTeclar(evento: KeyboardEvent) {
      const alvo = evento.target as HTMLElement | null;
      if (alvo && ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName)) return;
      if (evento.key === "a" || evento.key === "A") void decidir("aprovado");
      if (evento.key === "d" || evento.key === "D") void decidir("descartado");
    }
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [decidir]);

  if (conjunto.revisao_automatica) {
    return (
      <Moldura titulo={`${conjunto.nome} — sem fila`}>
        <p className="text-sm text-gray-600">
          Gabarito exato por construção, sem revisão humana: no conjunto de imagem ele é o nome da
          pasta do fornecedor, e no de banco as perguntas saem das próprias linhas de{" "}
          <code className="rounded bg-gray-100 px-1">produtos</code>.
        </p>
      </Moldura>
    );
  }

  if (!conjunto.existe) {
    return (
      <Moldura titulo={`${conjunto.nome} — não gerado`}>
        <p className="text-sm text-gray-600">
          O <code className="rounded bg-gray-100 px-1">dataset.json</code> deste conjunto ainda não
          existe. Gere o rascunho antes de revisar.
        </p>
      </Moldura>
    );
  }

  if (itens === null) {
    return (
      <Moldura titulo={`${conjunto.nome} — fila de revisão`}>
        <p className="text-sm text-gray-500">Carregando…</p>
      </Moldura>
    );
  }

  if (!atual) {
    return (
      <Moldura titulo={`${conjunto.nome} — fila de revisão`}>
        <p className="text-sm text-gray-600">
          {itens.length === 0
            ? "Nenhum item pendente."
            : "Fatia revisada. Carregue a próxima para seguir."}
        </p>
        <button
          type="button"
          onClick={() => void carregar()}
          className="mt-3 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Carregar próximos
        </button>
      </Moldura>
    );
  }

  return (
    <Moldura
      titulo={`${conjunto.nome} — fila de revisão`}
      direita={
        <span className="text-xs text-gray-500 tabular-nums">
          item {posicao + 1} de {itens.length} nesta fatia · {conjunto.pendentes} pendentes no total
        </span>
      }
    >
      <p className="text-xs text-gray-500">
        id <code className="rounded bg-gray-100 px-1">{atual.id}</code> · índice {atual.indice}
      </p>

      <div className="mt-3 space-y-3">
        {Object.entries(atual.campos).map(([chave, valor]) => (
          <Campo
            key={chave}
            chave={chave}
            valor={valor}
            editado={edicoes[chave]}
            onEditar={(texto) => setEdicoes((e) => ({ ...e, [chave]: texto }))}
          />
        ))}
      </div>

      {erro ? <p className="mt-3 text-sm text-red-600">{erro}</p> : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={salvando}
          onClick={() => void decidir("aprovado")}
          className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {Object.keys(edicoes).length > 0 ? "Salvar correção" : "Aprovar"}
          <kbd className="ml-2 rounded bg-emerald-700/40 px-1 text-[11px]">A</kbd>
        </button>
        <button
          type="button"
          disabled={salvando}
          onClick={() => void decidir("descartado")}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Descartar
          <kbd className="ml-2 rounded bg-gray-100 px-1 text-[11px]">D</kbd>
        </button>
        <button
          type="button"
          disabled={salvando || posicao === 0}
          onClick={() => {
            setPosicao((p) => Math.max(0, p - 1));
            setEdicoes({});
          }}
          className="rounded-md px-2 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40"
        >
          ← anterior
        </button>
        <span className="text-xs text-gray-500">
          O item descartado fica no arquivo com{" "}
          <code className="rounded bg-gray-100 px-1">revisao.status</code>; os scripts filtram por
          status.
        </span>
      </div>
    </Moldura>
  );
}

/** Campo editável para texto e número; o resto vai cru, só leitura. */
function Campo({
  chave,
  valor,
  editado,
  onEditar,
}: {
  chave: string;
  valor: unknown;
  editado: string | undefined;
  onEditar: (texto: string) => void;
}) {
  const editavel = typeof valor === "string" || typeof valor === "number";
  const texto = useMemo(
    () => (editavel ? String(editado ?? valor) : JSON.stringify(valor, null, 2)),
    [editavel, editado, valor],
  );
  const longo = editavel && texto.length > 80;

  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{chave}</span>
      {!editavel ? (
        <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-gray-50 p-2 text-xs text-gray-700">
          {texto}
        </pre>
      ) : longo ? (
        <textarea
          value={texto}
          rows={Math.min(10, Math.ceil(texto.length / 90) + 1)}
          onChange={(e) => onEditar(e.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm text-gray-900"
        />
      ) : (
        <input
          value={texto}
          onChange={(e) => onEditar(e.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm text-gray-900"
        />
      )}
    </label>
  );
}

function Moldura({
  titulo,
  direita,
  children,
}: {
  titulo: string;
  direita?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-gray-900">{titulo}</h2>
        {direita}
      </div>
      {children}
    </section>
  );
}

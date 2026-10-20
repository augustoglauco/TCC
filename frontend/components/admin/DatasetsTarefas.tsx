"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelarTarefa,
  fetchTarefa,
  fetchTarefas,
  iniciarTarefa,
  TAREFAS,
  type TarefaResumo,
} from "@/lib/api/datasets";

const INTERVALO_POLLING_MS = 2000;

/**
 * Disparo e acompanhamento das tarefas longas da Fase 10.
 *
 * O backend roda o processo solto porque ingestão leva minutos e o benchmark
 * leva horas — bloquear a requisição (padrão de `admin_ferramentas`) não
 * serviria. Aqui o log é pedido a partir do offset já exibido
 * (`desde`/`proximo_offset`), em vez de rebaixar o buffer inteiro a cada
 * volta.
 */
function useTarefas(token: string) {
  const [tarefas, setTarefas] = useState<TarefaResumo[]>([]);
  // O log guarda o id junto: trocar de tarefa troca o par inteiro, em vez
  // de precisar de um efeito que zere as linhas da anterior.
  const [log, setLog] = useState<{ id: string | null; linhas: string[] }>({
    id: null,
    linhas: [],
  });
  const [erro, setErro] = useState<string | null>(null);
  const offset = useRef(0);

  const carregarTarefas = useCallback(async () => {
    try {
      setTarefas(await fetchTarefas(token));
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Erro ao listar as tarefas.");
    }
  }, [token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregarTarefas();
  }, [carregarTarefas]);

  const selecionar = useCallback((id: string) => {
    offset.current = 0;
    setLog({ id, linhas: [] });
  }, []);

  useEffect(() => {
    const id = log.id;
    if (!id) return;
    let vivo = true;

    // `id` entra por parâmetro: dentro de uma declaração de função o
    // TypeScript não mantém o estreitamento do `if (!id) return` acima.
    async function puxar(idTarefa: string) {
      try {
        const detalhe = await fetchTarefa(idTarefa, offset.current, token);
        if (!vivo) return;
        if (detalhe.linhas.length > 0) {
          offset.current = detalhe.proximo_offset;
          setLog((atual) =>
            atual.id === detalhe.id
              ? { id: atual.id, linhas: [...atual.linhas, ...detalhe.linhas] }
              : atual,
          );
        }
        setTarefas((atuais) => atuais.map((t) => (t.id === detalhe.id ? { ...t, ...detalhe } : t)));
        if (detalhe.estado === "rodando" && vivo) {
          setTimeout(() => void puxar(idTarefa), INTERVALO_POLLING_MS);
        }
      } catch (err: unknown) {
        if (vivo) setErro(err instanceof Error ? err.message : "Erro ao ler o log.");
      }
    }

    void puxar(id);
    return () => {
      vivo = false;
    };
    // Só o id entra nas dependências: reagir a `log.linhas` reiniciaria o
    // polling a cada linha que ele mesmo acrescenta.
  }, [log.id, token]);

  const iniciar = async (tipo: string) => {
    setErro(null);
    try {
      const tarefa = await iniciarTarefa(tipo, token);
      await carregarTarefas();
      selecionar(tarefa.id);
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Erro ao iniciar a tarefa.");
    }
  };

  const cancelar = async (id: string) => {
    setErro(null);
    try {
      await cancelarTarefa(id, token);
      await carregarTarefas();
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : "Erro ao cancelar a tarefa.");
    }
  };

  const detalheSelecionado = tarefas.find((t) => t.id === log.id) ?? null;

  return { tarefas, log, erro, detalheSelecionado, selecionar, iniciar, cancelar };
}

export function DatasetsTarefas({ token }: { token: string }) {
  const { tarefas, log, erro, detalheSelecionado, selecionar, iniciar, cancelar } =
    useTarefas(token);

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-gray-900">Tarefas longas</h2>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {TAREFAS.map((t) => (
          <div key={t.tipo} className="rounded-md border border-gray-200 p-3">
            <p className="text-sm font-medium text-gray-900">{t.rotulo}</p>
            <p className="mt-1 text-xs text-gray-500">{t.descricao}</p>
            <button
              type="button"
              onClick={() => void iniciar(t.tipo)}
              className="mt-2 rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700"
            >
              Iniciar
            </button>
          </div>
        ))}
      </div>

      {erro ? <p className="mt-3 text-sm text-red-600">{erro}</p> : null}

      <ListaTarefas
        tarefas={tarefas}
        idSelecionado={log.id}
        onSelecionar={selecionar}
        onCancelar={(id) => void cancelar(id)}
      />

      {log.id ? (
        <div className="mt-3">
          <p className="mb-1 text-xs text-gray-500">
            Log de {detalheSelecionado?.rotulo ?? log.id}
            {detalheSelecionado?.estado === "rodando" ? " (atualizando)" : ""}
          </p>
          <pre className="max-h-72 overflow-auto rounded-md bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
            {log.linhas.length > 0 ? log.linhas.join("\n") : "sem saída ainda…"}
          </pre>
        </div>
      ) : null}
    </section>
  );
}

function ListaTarefas({
  tarefas,
  idSelecionado,
  onSelecionar,
  onCancelar,
}: {
  tarefas: TarefaResumo[];
  idSelecionado: string | null;
  onSelecionar: (id: string) => void;
  onCancelar: (id: string) => void;
}) {
  return (
    <>
      {tarefas.length > 0 ? (
        <ul className="mt-4 divide-y divide-gray-100">
          {tarefas.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 py-2">
              <EstadoSelo estado={t.estado} />
              <button
                type="button"
                onClick={() => onSelecionar(t.id)}
                className={`text-sm ${
                  t.id === idSelecionado
                    ? "font-semibold text-gray-900"
                    : "text-gray-700 hover:underline"
                }`}
              >
                {t.rotulo}
              </button>
              <span className="text-xs text-gray-400 tabular-nums">
                {new Date(t.iniciada_em * 1000).toLocaleTimeString("pt-BR")} · {t.total_linhas}{" "}
                linhas
                {t.codigo !== null ? ` · código ${t.codigo}` : ""}
              </span>
              {t.estado === "rodando" ? (
                <button
                  type="button"
                  onClick={() => onCancelar(t.id)}
                  className="ml-auto rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50"
                >
                  Cancelar
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-gray-500">
          Nenhuma tarefa iniciada nesta sessão do backend.
        </p>
      )}
    </>
  );
}

function EstadoSelo({ estado }: { estado: string }) {
  const estilo =
    estado === "rodando"
      ? "border-sky-200 bg-sky-50 text-sky-700"
      : estado === "concluida"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-red-200 bg-red-50 text-red-700";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${estilo}`}>
      {estado}
    </span>
  );
}

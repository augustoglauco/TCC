"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { fetchResultadosAvaliacao, Proporcao, ResultadosAvaliacao } from "@/lib/api/avaliacao";

// Uma cor por modelo no gráfico de dispersão (legenda + rótulo ao lado do ponto).
const CORES_MODELOS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#0891b2"];

const pct = (v: number) => Math.round(v * 1000) / 10;

function comIc(nome: string, p: Proporcao) {
  return {
    nome,
    valor: pct(p.taxa),
    erro: [pct(p.taxa - p.ic_inf), pct(p.ic_sup - p.taxa)] as [number, number],
    n: `${p.acertos}/${p.total}`,
  };
}

function Secao({
  titulo,
  descricao,
  children,
}: {
  titulo: string;
  descricao: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900">{titulo}</h2>
      <p className="mb-4 text-sm text-gray-600">{descricao}</p>
      {children}
    </section>
  );
}

function Vazio({ comando }: { comando: string }) {
  return (
    <p className="rounded-md bg-gray-50 p-4 text-sm text-gray-600">
      Ainda não rodou. Execute <code className="rounded bg-gray-200 px-1">{comando}</code> na
      máquina com GPU.
    </p>
  );
}

function Cartao({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="rounded-md border border-gray-200 p-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">{rotulo}</div>
      <div className="text-2xl font-semibold text-gray-900">{valor}</div>
    </div>
  );
}

function BarrasComIc({ dados, rotulo }: { dados: ReturnType<typeof comIc>[]; rotulo: string }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={dados} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="nome" />
          <YAxis domain={[0, 100]} unit="%" />
          <Tooltip formatter={(v) => [`${v}%`, rotulo]} />
          <Bar dataKey="valor" fill="#2563eb" name={rotulo}>
            <ErrorBar dataKey="erro" width={6} stroke="#111827" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function MapaCalor({
  dominios,
  matriz,
}: {
  dominios: string[];
  matriz: Record<string, Record<string, number>>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead>
          <tr>
            <th className="p-2 text-left text-xs text-gray-500">esperado ↓ / previsto →</th>
            {dominios.map((d) => (
              <th key={d} className="p-2 text-xs capitalize text-gray-700">
                {d}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dominios.map((esperado) => {
            const linha = matriz[esperado] ?? {};
            const total = dominios.reduce((s, d) => s + (linha[d] ?? 0), 0) || 1;
            return (
              <tr key={esperado}>
                <th className="p-2 text-left text-xs capitalize text-gray-700">{esperado}</th>
                {dominios.map((previsto) => {
                  const n = linha[previsto] ?? 0;
                  const diag = esperado === previsto;
                  const alpha = Math.max(0.05, n / total);
                  return (
                    <td
                      key={previsto}
                      className="h-12 w-20 text-center font-medium"
                      style={{
                        background:
                          n === 0
                            ? "#f9fafb"
                            : diag
                              ? `rgba(16,185,129,${alpha})`
                              : `rgba(239,68,68,${alpha})`,
                      }}
                    >
                      {n}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type DadosRoteador = NonNullable<ResultadosAvaliacao["roteador"]>;
type DadosRag = NonNullable<ResultadosAvaliacao["rag"]>;
type DadosEtapa7 = NonNullable<ResultadosAvaliacao["etapa7"]>;
type DadosChunkSize = NonNullable<ResultadosAvaliacao["chunk_size"]>;
type DadosInjecao = NonNullable<ResultadosAvaliacao["injecao"]>;
type ModeloBenchmark = ResultadosAvaliacao["modelos"][number];

// "Gemma-4-E4B-it UD-Q8_K_XL" -> "Gemma-4-E4B-it": o sufixo de quantização só polui o eixo.
const nomeCurto = (nome: string) => nome.split(" ").slice(0, 2).join(" ");

const pctOuTraco = (v: number | null | undefined) => (v != null ? `${pct(v)}%` : "—");

function SecaoModelos({ modelos }: { modelos: ModeloBenchmark[] }) {
  // Só quem rodou a etapa de RAG tem nota e ponto no gráfico (os da triagem não).
  const comRag = modelos.filter(
    (m) => m.metricas.rag_nota_media != null && m.metricas.latencia_p95_s != null,
  );
  return (
    <Secao
      titulo="Comparativo de modelos locais"
      descricao="Qualidade × latência de cada modelo candidato, medidos contra o sistema completo. Quanto mais ao alto e à esquerda, melhor."
    >
      {comRag.length === 0 ? (
        <Vazio comando="python eval/model_benchmark/run_benchmark.py" />
      ) : (
        <div className="space-y-8">
          <div className="h-[26rem]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 16, right: 32, bottom: 16, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="latencia"
                  name="Latência p95"
                  unit=" s"
                  domain={[0, 10]}
                  ticks={[0, 2, 4, 6, 8, 10]}
                  tick={{ fontSize: 13 }}
                  label={{ value: "Latência p95 (s)", position: "insideBottom", offset: -8 }}
                />
                <YAxis
                  type="number"
                  dataKey="qualidade"
                  name="Nota RAG"
                  domain={[2, 5]}
                  tick={{ fontSize: 13 }}
                  label={{ value: "Nota RAG (1–5)", angle: -90, position: "insideLeft" }}
                />
                <ZAxis range={[220, 220]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} labelFormatter={() => ""} />
                <Legend verticalAlign="bottom" wrapperStyle={{ paddingTop: 16, fontSize: 14 }} />
                {comRag.map((m, i) => (
                  <Scatter
                    key={m.modelo}
                    name={nomeCurto(m.modelo)}
                    fill={CORES_MODELOS[i % CORES_MODELOS.length]}
                    data={[
                      {
                        latencia: m.metricas.latencia_p95_s,
                        qualidade: m.metricas.rag_nota_media,
                      },
                    ]}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={comRag.map((m) => ({
                  modelo: nomeCurto(m.modelo),
                  Roteador:
                    m.metricas.roteador_acuracia != null ? pct(m.metricas.roteador_acuracia) : null,
                  Injeção:
                    m.metricas.injecao_resistencia != null
                      ? pct(m.metricas.injecao_resistencia)
                      : null,
                }))}
                margin={{ top: 16, right: 32, left: 0, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="modelo" tick={{ fontSize: 13 }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 13 }} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend wrapperStyle={{ paddingTop: 8, fontSize: 14 }} />
                <Bar dataKey="Roteador" fill="#2563eb" />
                <Bar dataKey="Injeção" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500">
                  <th className="p-2">Modelo</th>
                  <th className="p-2">Roteador</th>
                  <th className="p-2">Nota RAG</th>
                  <th className="p-2">Injeção</th>
                  <th className="p-2">Latência p95</th>
                </tr>
              </thead>
              <tbody>
                {comRag.map((m, i) => (
                  <tr key={m.modelo} className="border-t border-gray-100">
                    <td className="p-2">
                      <span
                        className="mr-2 inline-block h-3 w-3 rounded-full align-middle"
                        style={{ background: CORES_MODELOS[i % CORES_MODELOS.length] }}
                      />
                      {m.modelo}
                    </td>
                    <td className="p-2">{pctOuTraco(m.metricas.roteador_acuracia)}</td>
                    <td className="p-2">{m.metricas.rag_nota_media?.toFixed(2) ?? "—"}</td>
                    <td className="p-2">{pctOuTraco(m.metricas.injecao_resistencia)}</td>
                    <td className="p-2">{m.metricas.latencia_p95_s?.toFixed(1)} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Secao>
  );
}

function SecaoRoteador({
  roteador,
  provedor,
  onProvedor,
}: {
  roteador: DadosRoteador | null | undefined;
  provedor: string | null;
  onProvedor: (v: string) => void;
}) {
  const matrizAtual = roteador?.provedores.find((p) => p.provider === provedor);
  return (
    <Secao
      titulo="Roteador de intenções"
      descricao="Acurácia por provedor e matriz de confusão entre os quatro domínios."
    >
      {!roteador ? (
        <Vazio comando="python eval/router_intents/run_eval.py" />
      ) : (
        <div className="space-y-6">
          <BarrasComIc
            rotulo="Acurácia"
            dados={roteador.provedores.map((p) => comIc(p.provider, p.acuracia))}
          />
          <div>
            <label className="mb-2 block text-sm text-gray-700">
              Matriz de confusão do provedor:{" "}
              <select
                className="rounded border border-gray-300 px-2 py-1"
                value={provedor ?? ""}
                onChange={(e) => onProvedor(e.target.value)}
              >
                {roteador.provedores.map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.provider}
                  </option>
                ))}
              </select>
            </label>
            {matrizAtual && (
              <MapaCalor dominios={roteador.dominios} matriz={matrizAtual.matriz_confusao} />
            )}
          </div>
        </div>
      )}
    </Secao>
  );
}

function SecaoRag({ rag }: { rag: DadosRag | null | undefined }) {
  return (
    <Secao
      titulo="Qualidade do RAG"
      descricao="Nota do juiz (1–5) e se a fonte correta foi recuperada — separa erro de recuperação de erro de geração."
    >
      {!rag ? (
        <Vazio comando="python eval/rag_quality/run_eval.py" />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Cartao rotulo="Perguntas" valor={String(rag.total)} />
            <Cartao rotulo="Nota média" valor={rag.nota_media?.toFixed(2) ?? "—"} />
            <Cartao rotulo="Fonte correta" valor={`${pct(rag.fonte_correta.taxa)}%`} />
            <Cartao
              rotulo="Nota c/ fonte certa × errada"
              valor={`${rag.nota_media_fonte_certa?.toFixed(1) ?? "—"} × ${rag.nota_media_fonte_errada?.toFixed(1) ?? "—"}`}
            />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={Object.entries(rag.distribuicao_notas).map(([nota, n]) => ({ nota, n }))}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="nota"
                    label={{ value: "Nota", position: "insideBottom", offset: -2 }}
                  />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="n" name="Perguntas" fill="#2563eb" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rag.por_dificuldade}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="dificuldade" />
                  <YAxis domain={[0, 5]} />
                  <Tooltip />
                  <Bar dataKey="nota_media" name="Nota média" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Cartao rotulo="Sem resposta no corpus" valor={String(rag.sem_resposta.total)} />
            <Cartao
              rotulo="Recusou (correto)"
              valor={`${rag.sem_resposta.recusou}/${rag.sem_resposta.total}`}
            />
            <Cartao
              rotulo="Inventou resposta"
              valor={`${rag.sem_resposta.alucinou}/${rag.sem_resposta.total}`}
            />
          </div>
        </div>
      )}
    </Secao>
  );
}

function SecaoEtapa7({ etapa7 }: { etapa7: DadosEtapa7 | null | undefined }) {
  return (
    <Secao
      titulo="Configuração do RAG: antes × depois"
      descricao="Ponto de partida (MiniLM, chunks de 800 caracteres) contra a configuração escolhida (bge-m3, 768 tokens, top_k 5), no mesmo conjunto de perguntas e com o mesmo juiz."
    >
      {!etapa7 ? (
        <Vazio comando="python eval/rag_quality/consolidar_etapa7.py" />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={etapa7.bracos.map((b) => ({
                    ...comIc(b.rotulo, b.fonte_correta_ic),
                    nome: b.braco === "baseline" ? "Antes" : "Depois",
                  }))}
                  margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="nome" />
                  <YAxis domain={[0, 100]} unit="%" />
                  <Tooltip formatter={(v) => [`${v}%`, "Fonte correta"]} />
                  <Bar dataKey="valor" fill="#2563eb" name="Fonte correta">
                    <ErrorBar dataKey="erro" width={6} stroke="#111827" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={etapa7.bracos.map((b) => ({
                    nome: b.braco === "baseline" ? "Antes" : "Depois",
                    Nota: b.nota_media,
                    "Recusas indevidas": b.recusas_indevidas,
                  }))}
                  margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="nome" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="Nota" fill="#10b981" />
                  <Bar dataKey="Recusas indevidas" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="p-2">Configuração</th>
                <th className="p-2">Nota</th>
                <th className="p-2">Fonte correta</th>
                <th className="p-2">Recusa correta (sem resposta no corpus)</th>
                <th className="p-2">Latência média / p95</th>
              </tr>
            </thead>
            <tbody>
              {etapa7.bracos.map((b) => (
                <tr key={b.braco} className="border-t border-gray-100">
                  <td className="p-2">{b.rotulo}</td>
                  <td className="p-2">{b.nota_media.toFixed(2)}</td>
                  <td className="p-2">
                    {b.fonte_correta}/{b.respondiveis}
                  </td>
                  <td className="p-2">
                    {b.negativas_recusou}/{b.sem_resposta}
                  </td>
                  <td className="p-2">
                    {b.latencia_media_s.toFixed(1)} s / {b.latencia_p95_s.toFixed(1)} s
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Secao>
  );
}

function SecaoChunkSize({ chunk_size }: { chunk_size: DadosChunkSize | null | undefined }) {
  return (
    <Secao
      titulo="Tamanho de chunk"
      descricao="nDCG@10 e Recall@5 por chunk_size em tokens (melhor overlap de cada tamanho)."
    >
      {!chunk_size ? (
        <Vazio comando="python eval/rag_ingestion/run_etapa3.py" />
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chunk_size.pontos.map((p) => ({
                ...p,
                ndcg: p.ndcg_10 != null ? pct(p.ndcg_10) : null,
                recall: p.recall_5 != null ? pct(p.recall_5) : null,
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="chunk_size" />
              <YAxis domain={[0, 100]} unit="%" />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="ndcg" name="nDCG@10" stroke="#2563eb" />
              <Line type="monotone" dataKey="recall" name="Recall@5" stroke="#10b981" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Secao>
  );
}

function SecaoInjecao({ injecao }: { injecao: DadosInjecao | null | undefined }) {
  return (
    <Secao
      titulo="Resistência a prompt injection"
      descricao="Proporção de casos em que o modelo NÃO obedeceu à instrução injetada."
    >
      {!injecao ? (
        <Vazio comando="python eval/prompt_injection/run_eval.py" />
      ) : (
        <div className="space-y-4">
          <BarrasComIc
            rotulo="Resistência"
            dados={injecao.clientes.map((c) => comIc(c.cliente, c.resistencia))}
          />
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500">
                <th className="p-2">Cliente</th>
                <th className="p-2">Categoria</th>
                <th className="p-2">Casos</th>
                <th className="p-2">Comprometidos</th>
              </tr>
            </thead>
            <tbody>
              {injecao.clientes.flatMap((c) =>
                c.por_categoria.map((cat) => (
                  <tr key={`${c.cliente}-${cat.categoria}`} className="border-t border-gray-100">
                    <td className="p-2">{c.cliente}</td>
                    <td className="p-2">{cat.categoria}</td>
                    <td className="p-2">{cat.total}</td>
                    <td className="p-2">{cat.comprometidos}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      )}
    </Secao>
  );
}

export default function AvaliacaoPage() {
  const [dados, setDados] = useState<ResultadosAvaliacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [provedor, setProvedor] = useState<string | null>(null);

  useEffect(() => {
    fetchResultadosAvaliacao()
      .then((d) => {
        setDados(d);
        setProvedor(d.roteador?.provedores.at(-1)?.provider ?? null);
      })
      .catch((e: Error) => setErro(e.message));
  }, []);

  if (erro) return <main className="mx-auto max-w-5xl p-6 text-red-700">{erro}</main>;
  if (!dados)
    return <main className="mx-auto max-w-5xl p-6 text-gray-600">Carregando resultados…</main>;

  const { roteador, rag, etapa7, chunk_size, injecao, modelos } = dados;

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Resultados da avaliação experimental</h1>
        <p className="text-sm text-gray-600">
          Métricas agregadas do roteador, do RAG, da resistência a prompt injection e do benchmark
          de modelos locais. As barras de erro são intervalos de confiança de 95% (Wilson): se duas
          barras se sobrepõem, a diferença não é estatisticamente distinguível com essa amostra.
        </p>
      </header>
      <SecaoModelos modelos={modelos} />
      <SecaoRoteador roteador={roteador} provedor={provedor} onProvedor={setProvedor} />
      <SecaoRag rag={rag} />
      <SecaoEtapa7 etapa7={etapa7} />
      <SecaoChunkSize chunk_size={chunk_size} />
      <SecaoInjecao injecao={injecao} />
    </main>
  );
}

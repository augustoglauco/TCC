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
import { Modal } from "@/components/ui/Modal";
import { DETALHES } from "./detalhes";
import { GRUPOS_PROMPTS, MECANICA, type TabelaSimples } from "./prompts";
import { TRAJETORIA } from "./trajetoria";
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
    <section className="relative rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
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

/** Badge "i": o balão com a explicação abre ao passar o mouse ou ao focar (teclado). */
function Info({ texto }: { texto: string }) {
  return (
    <span className="group ml-2 inline-flex align-middle">
      <button
        type="button"
        aria-label="Sobre este gráfico"
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold italic leading-none text-blue-700 hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute right-4 z-20 mt-6 w-72 max-w-[80vw] rounded-md bg-gray-900 p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-white opacity-0 shadow-lg group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        {texto}
      </span>
    </span>
  );
}

type Celula = string | number | null;
interface Tabela {
  colunas: string[];
  linhas: Celula[][];
}

/** Tabela de dados que originou um gráfico, no formato do modal de detalhes. */
function tabelaDeIc(dados: ReturnType<typeof comIc>[], rotuloValor: string): Tabela {
  return {
    colunas: ["Item", rotuloValor, "IC 95%", "Acertos"],
    linhas: dados.map((d) => [
      d.nome,
      `${d.valor}%`,
      `${Math.round((d.valor - d.erro[0]) * 10) / 10}% – ${Math.round((d.valor + d.erro[1]) * 10) / 10}%`,
      d.n,
    ]),
  };
}

function Secao2({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="mb-4">
      <h4 className="mb-1 text-sm font-semibold text-gray-900">{titulo}</h4>
      {children}
    </section>
  );
}

/** Modal "detalhes": explicação, tabela de origem, motivo, relevância, cuidados e trajetória. */
function DetalheModal({
  chave,
  titulo,
  ajuda,
  tabela,
  open,
  onOpenChange,
}: {
  chave: string;
  titulo: string;
  ajuda: string;
  tabela?: Tabela;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const d = DETALHES[chave];
  return (
    <Modal open={open} onOpenChange={onOpenChange} title={titulo} size="3xl">
      <div className="text-sm leading-relaxed text-gray-700">
        <Secao2 titulo="O que o gráfico mostra">
          <p>{ajuda}</p>
        </Secao2>
        {tabela && (
          <Secao2 titulo="Tabela que originou o gráfico">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-500">
                    {tabela.colunas.map((c) => (
                      <th key={c} className="p-1.5">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tabela.linhas.map((l, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      {l.map((c, j) => (
                        <td key={j} className="p-1.5">
                          {c ?? "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Secao2>
        )}
        {d && (
          <>
            <Secao2 titulo="Por que medimos isto">
              <p>{d.motivo}</p>
            </Secao2>
            <Secao2 titulo="Relevância">
              <p>{d.relevancia}</p>
            </Secao2>
            <Secao2 titulo="Considerações e cuidados na leitura">
              <ul className="list-disc space-y-1 pl-5">
                {d.consideracoes.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </Secao2>
            <Secao2 titulo="Como chegamos a esta conclusão">
              <p>{d.trajetoria}</p>
            </Secao2>
          </>
        )}
      </div>
    </Modal>
  );
}

/** Título de um gráfico/tabela com o badge de ajuda (balão) e, se houver `detalhe`, o badge do modal. */
function Grafico({
  titulo,
  ajuda,
  className,
  children,
  detalhe,
  tabela,
}: {
  titulo: string;
  ajuda: string;
  className?: string;
  children: React.ReactNode;
  detalhe?: string;
  tabela?: Tabela;
}) {
  const [aberto, setAberto] = useState(false);
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-gray-800">
        {titulo}
        <Info texto={ajuda} />
        {detalhe && (
          <>
            <button
              type="button"
              aria-label={`Detalhes: ${titulo}`}
              title="Detalhes, tabela de origem e como chegamos a esta conclusão"
              onClick={() => setAberto(true)}
              className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full bg-violet-100 align-middle text-[11px] font-bold leading-none text-violet-700 hover:bg-violet-200 focus:outline-none focus:ring-2 focus:ring-violet-400"
            >
              +
            </button>
            <DetalheModal
              chave={detalhe}
              titulo={titulo}
              ajuda={ajuda}
              tabela={tabela}
              open={aberto}
              onOpenChange={setAberto}
            />
          </>
        )}
      </h3>
      <div className={className}>{children}</div>
    </div>
  );
}

function Cartao({ rotulo, valor, ajuda }: { rotulo: string; valor: string; ajuda?: string }) {
  return (
    <div className="rounded-md border border-gray-200 p-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">
        {rotulo}
        {ajuda && <Info texto={ajuda} />}
      </div>
      <div className="text-2xl font-semibold text-gray-900">{valor}</div>
    </div>
  );
}

function BarrasComIc({
  dados,
  rotulo,
  titulo,
  ajuda,
  detalhe,
}: {
  dados: ReturnType<typeof comIc>[];
  rotulo: string;
  titulo: string;
  ajuda: string;
  detalhe?: string;
}) {
  return (
    <Grafico
      titulo={titulo}
      ajuda={ajuda}
      className="h-64"
      detalhe={detalhe}
      tabela={tabelaDeIc(dados, rotulo)}
    >
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
    </Grafico>
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
          <Grafico
            titulo="Qualidade × latência"
            detalhe="qualidadeLatencia"
            tabela={{
              colunas: ["Modelo", "Latência p95 (s)", "Nota RAG"],
              linhas: comRag.map((m) => [
                m.modelo,
                m.metricas.latencia_p95_s?.toFixed(2) ?? null,
                m.metricas.rag_nota_media?.toFixed(2) ?? null,
              ]),
            }}
            ajuda="Cada ponto é um modelo. Eixo horizontal: latência p95 (95% das respostas saem mais rápido que esse tempo). Eixo vertical: nota média do juiz (1 a 5) nas respostas de RAG. Quanto mais ao alto e à esquerda, melhor: resposta boa e rápida."
            className="h-[26rem]"
          >
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
          </Grafico>
          <Grafico
            titulo="Roteador e resistência à injeção"
            detalhe="roteadorInjecaoModelos"
            tabela={{
              colunas: ["Modelo", "Roteador", "Injeção"],
              linhas: comRag.map((m) => [
                m.modelo,
                pctOuTraco(m.metricas.roteador_acuracia),
                pctOuTraco(m.metricas.injecao_resistencia),
              ]),
            }}
            ajuda="Para cada modelo: em azul, a porcentagem de mensagens que o roteador classificou no domínio certo (vendas, suporte, atendimento, agendamento); em laranja, a porcentagem de ataques de prompt injection que o modelo resistiu, isto é, não obedeceu à instrução maliciosa. Maior é melhor."
            className="h-80"
          >
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
          </Grafico>
          <Grafico
            titulo="Resumo numérico"
            detalhe="resumoModelos"
            ajuda="Os mesmos valores dos dois gráficos acima, em números. A bolinha tem a cor do ponto no gráfico de qualidade × latência."
            className="overflow-x-auto"
          >
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
          </Grafico>
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
            titulo="Acurácia por método"
            detalhe="roteadorAcuracia"
            ajuda="Porcentagem de mensagens classificadas no domínio correto, por método: heurística (palavras-chave), heurística + LLM (modelo local) e JEV (modelo externo). A barra preta é o intervalo de confiança de 95%: se duas barras se sobrepõem, a diferença pode ser acaso."
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
              <Grafico
                titulo="Matriz de confusão"
                detalhe="matrizConfusao"
                tabela={{
                  colunas: ["Real \\ Previsto", ...roteador.dominios],
                  linhas: roteador.dominios.map((real) => [
                    real,
                    ...roteador.dominios.map(
                      (prev) => matrizAtual.matriz_confusao[real]?.[prev] ?? 0,
                    ),
                  ]),
                }}
                ajuda="Cada linha é o domínio correto; cada coluna, o que o roteador previu. A diagonal verde são os acertos; as células vermelhas, os erros (por exemplo, uma mensagem de vendas classificada como agendamento). Quanto mais forte a cor, mais casos."
              >
                <MapaCalor dominios={roteador.dominios} matriz={matrizAtual.matriz_confusao} />
              </Grafico>
            )}
          </div>
        </div>
      )}
    </Secao>
  );
}

function SecaoRag({ rag }: { rag: DadosRag | null | undefined }) {
  const notas = rag?.distribuicao_notas ?? {};
  const totalNotas = Object.values(notas).reduce((s, n) => s + n, 0) || 1;
  const pct4e5 = Math.round((((notas["4"] ?? 0) + (notas["5"] ?? 0)) / totalNotas) * 100);
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
            <Cartao
              rotulo="Fonte correta"
              valor={`${pct(rag.fonte_correta.taxa)}%`}
              ajuda="Em quantas perguntas o documento certo estava entre os trechos recuperados pela busca. Mede só a recuperação, separada da geração da resposta."
            />
            <Cartao
              rotulo="Nota c/ fonte certa × errada"
              ajuda="Nota média do juiz quando a busca trouxe o documento certo × quando não trouxe. A diferença mostra o quanto uma busca errada limita a qualidade da resposta."
              valor={`${rag.nota_media_fonte_certa?.toFixed(1) ?? "—"} × ${rag.nota_media_fonte_errada?.toFixed(1) ?? "—"}`}
            />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <Grafico
              titulo="Distribuição das notas"
              detalhe="distribuicaoNotas"
              tabela={{
                colunas: ["Nota", "Perguntas"],
                linhas: Object.entries(rag.distribuicao_notas),
              }}
              ajuda={`Quantas perguntas receberam cada nota do juiz (um LLM que compara a resposta com o gabarito), de 1 (errada ou inútil) a 5 (correta, relevante e fundamentada na fonte). ${pct4e5}% das perguntas ficaram em 4 ou 5; as notas 1 e 2 são as falhas.`}
              className="h-56"
            >
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
            </Grafico>
            <Grafico
              titulo="Nota média por dificuldade"
              detalhe="dificuldade"
              tabela={{
                colunas: ["Dificuldade", "Nota média"],
                linhas: rag.por_dificuldade.map((d) => [
                  d.dificuldade,
                  d.nota_media?.toFixed(2) ?? null,
                ]),
              }}
              ajuda="Nota média do juiz (1 a 5) por faixa de dificuldade da pergunta. Barras parecidas indicam que o sistema não piora muito em perguntas mais difíceis."
              className="h-56"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rag.por_dificuldade}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="dificuldade" />
                  <YAxis domain={[0, 5]} />
                  <Tooltip />
                  <Bar dataKey="nota_media" name="Nota média" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </Grafico>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Cartao
              rotulo="Sem resposta no corpus"
              valor={String(rag.sem_resposta.total)}
              ajuda="Perguntas cuja resposta não está em nenhum documento. O comportamento certo é admitir que não sabe, sem inventar."
            />
            <Cartao
              rotulo="Recusou (correto)"
              ajuda="Das perguntas sem resposta no corpus, quantas o modelo admitiu não saber. Maior é melhor."
              valor={`${rag.sem_resposta.recusou}/${rag.sem_resposta.total}`}
            />
            <Cartao
              rotulo="Inventou resposta"
              ajuda="Das perguntas sem resposta no corpus, quantas o modelo respondeu mesmo assim, sem base nos documentos (alucinação). Menor é melhor."
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
            <Grafico
              titulo="Fonte correta: antes × depois"
              detalhe="etapa7Fonte"
              tabela={tabelaDeIc(
                etapa7.bracos.map((b) => comIc(b.rotulo, b.fonte_correta_ic)),
                "Fonte correta",
              )}
              ajuda="Porcentagem de perguntas em que o documento certo foi recuperado, antes (MiniLM, chunks de 800 caracteres) e depois (bge-m3, 768 tokens, top_k 5). A barra preta é o intervalo de confiança de 95%: sem sobreposição, a melhora é real."
              className="h-64"
            >
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
            </Grafico>
            <Grafico
              titulo="Nota e recusas indevidas"
              detalhe="etapa7Nota"
              tabela={{
                colunas: ["Configuração", "Nota média", "Recusas indevidas"],
                linhas: etapa7.bracos.map((b) => [
                  b.rotulo,
                  b.nota_media.toFixed(2),
                  b.recusas_indevidas,
                ]),
              }}
              ajuda="Em verde, a nota média do juiz (1 a 5). Em vermelho, quantas respostas disseram “não encontrei” mesmo havendo a resposta no corpus: a busca antiga falhava e o modelo desistia; a nova reduz muito isso."
              className="h-64"
            >
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
            </Grafico>
          </div>
          <Grafico
            titulo="Resumo numérico"
            detalhe="resumoEtapa7"
            ajuda="Os valores dos dois gráficos acima, mais a recusa correta nas perguntas sem resposta no corpus e a latência de geração (média / p95)."
          >
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
          </Grafico>
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
        <Grafico
          titulo="Recuperação por tamanho de chunk"
          detalhe="chunkSize"
          tabela={{
            colunas: ["chunk_size (tokens)", "nDCG@10", "Recall@5"],
            linhas: chunk_size.pontos.map((p) => [
              p.chunk_size,
              p.ndcg_10 != null ? `${pct(p.ndcg_10)}%` : null,
              p.recall_5 != null ? `${pct(p.recall_5)}%` : null,
            ]),
          }}
          ajuda="Chunk é o pedaço de texto em que cada documento é dividido para a busca. nDCG@10 (azul): o documento certo aparece bem posicionado entre os 10 primeiros. Recall@5 (verde): o documento certo está entre os 5 primeiros. Curvas altas e planas indicam que o tamanho importa pouco."
          className="h-64"
        >
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
        </Grafico>
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
            titulo="Resistência por modelo"
            detalhe="injecaoResistencia"
            ajuda="Porcentagem de ataques de prompt injection que o modelo resistiu (não obedeceu à instrução maliciosa), para o modelo local e o externo. A barra preta é o intervalo de confiança de 95%. Maior é melhor."
            rotulo="Resistência"
            dados={injecao.clientes.map((c) => comIc(c.cliente, c.resistencia))}
          />
          <Grafico
            titulo="Casos por categoria"
            detalhe="injecaoCategorias"
            ajuda="Injeção direta: a instrução maliciosa está na própria mensagem do usuário. Injeção indireta via RAG: ela está escondida num documento recuperado. “Comprometidos” é quantas vezes o modelo obedeceu ao ataque; menos é melhor."
          >
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
          </Grafico>
        </div>
      )}
    </Secao>
  );
}

const BOTAO_CABECALHO =
  "inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-200 focus:outline-none focus:ring-2 focus:ring-violet-400";
const BOTAO_CABECALHO_ICONE =
  "inline-flex h-4 w-4 items-center justify-center rounded-full bg-violet-600 text-[11px] leading-none text-white";

/** Texto com `trechos` entre crases renderizados como código. */
function TextoRico({ texto }: { texto: string }) {
  return (
    <>
      {texto.split("`").map((parte, i) =>
        i % 2 === 1 ? (
          <code key={i} className="rounded bg-gray-100 px-1 py-0.5 text-[0.85em] text-gray-800">
            {parte}
          </code>
        ) : (
          <span key={i}>{parte}</span>
        ),
      )}
    </>
  );
}

function TabelaMecanica({ tabela }: { tabela: TabelaSimples }) {
  return (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-gray-500">
            {tabela.colunas.map((col) => (
              <th key={col} className="p-1.5">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tabela.linhas.map((l) => (
            <tr key={l[0]} className="border-t border-gray-100 align-top">
              {l.map((cel, j) => (
                <td key={j} className="p-1.5">
                  <TextoRico texto={cel} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AbaMecanica() {
  return (
    <div className="space-y-6">
      {MECANICA.map((b) => (
        <section key={b.titulo}>
          <h4 className="mb-2 text-base font-semibold text-gray-900">{b.titulo}</h4>
          {b.paragrafos.map((p) => (
            <p key={p} className="mb-2">
              <TextoRico texto={p} />
            </p>
          ))}
          {b.tabela && <TabelaMecanica tabela={b.tabela} />}
          {b.passos && (
            <ol className="space-y-2">
              {b.passos.map((s) => (
                <li key={s.titulo} className="rounded-lg border border-gray-100 bg-gray-50 p-2.5">
                  <p className="font-medium text-gray-900">{s.titulo}</p>
                  <p className="text-gray-700">
                    <TextoRico texto={s.texto} />
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      ))}
    </div>
  );
}

function AbaPrompts() {
  return (
    <div className="space-y-6">
      <p className="rounded-lg bg-violet-50 p-3 text-xs text-violet-900">
        Variáveis entre chaves (como {"{mensagem}"}) são preenchidas em tempo de execução. Textos
        longos aparecem abreviados; o texto completo de cada prompt está em{" "}
        <code>docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md</code> e no arquivo indicado em cada item.
      </p>
      {GRUPOS_PROMPTS.map((g) => (
        <section key={g.titulo}>
          <h4 className="mb-1 text-base font-semibold text-gray-900">{g.titulo}</h4>
          <p className="mb-3 text-gray-600">
            <TextoRico texto={g.intro} />
          </p>
          <div className="space-y-3">
            {g.prompts.map((p) => (
              <article key={p.nome} className="rounded-lg border border-gray-200 p-3">
                <h5 className="font-semibold text-gray-900">{p.nome}</h5>
                <dl className="mt-1 grid gap-x-3 gap-y-0.5 text-xs text-gray-600 sm:grid-cols-[auto_1fr]">
                  <dt className="font-medium">Quando roda</dt>
                  <dd>{p.quando}</dd>
                  <dt className="font-medium">Modelo</dt>
                  <dd>{p.modelo}</dd>
                  <dt className="font-medium">Arquivo</dt>
                  <dd className="break-all font-mono">{p.arquivo}</dd>
                </dl>
                <p className="mt-2 text-gray-700">
                  <TextoRico texto={p.explicacao} />
                </p>
                {p.texto && (
                  <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
                    {p.texto}
                  </pre>
                )}
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/** Botão do cabeçalho: abre o modal com a mecânica do roteador (regras, LLM local, Jev) e todos os prompts por função. */
function PromptsEMecanica() {
  const [aberto, setAberto] = useState(false);
  const [aba, setAba] = useState<"mecanica" | "prompts">("mecanica");
  const abas = [
    { id: "mecanica", rotulo: "Mecânica do roteador" },
    { id: "prompts", rotulo: "Prompts por função" },
  ] as const;
  return (
    <>
      <button type="button" onClick={() => setAberto(true)} className={BOTAO_CABECALHO}>
        <span className={BOTAO_CABECALHO_ICONE}>+</span>
        Prompts e mecânica do roteador
      </button>
      <Modal
        open={aberto}
        onOpenChange={setAberto}
        title="Prompts e mecânica do roteador"
        description="Como uma mensagem é classificada (regras, LLM local, TypeSafe Jev) e cada prompt enviado a um modelo, por função"
        size="3xl"
      >
        <div className="text-sm leading-relaxed text-gray-700">
          <div role="tablist" className="mb-4 flex gap-2 border-b border-gray-200">
            {abas.map((a) => (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={aba === a.id}
                onClick={() => setAba(a.id)}
                className={`-mb-px border-b-2 px-3 py-1.5 text-sm font-medium ${
                  aba === a.id
                    ? "border-violet-600 text-violet-700"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {a.rotulo}
              </button>
            ))}
          </div>
          {aba === "mecanica" ? <AbaMecanica /> : <AbaPrompts />}
        </div>
      </Modal>
    </>
  );
}

/** Badge geral do cabeçalho: abre o modal com a trajetória do projeto, do plano inicial às conclusões. */
function TrajetoriaCompleta() {
  const [aberto, setAberto] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        className={BOTAO_CABECALHO}
      >
        <span className={BOTAO_CABECALHO_ICONE}>+</span>
        Trajetória completa do experimento
      </button>
      <Modal
        open={aberto}
        onOpenChange={setAberto}
        title="Trajetória completa do experimento"
        description="Do plano inicial às conclusões: modelos, testes, ajustes de método, prompts e pontuação"
        size="3xl"
      >
        <div className="space-y-6 text-sm leading-relaxed text-gray-700">
          {TRAJETORIA.map((c) => (
            <section key={c.titulo}>
              <h4 className="mb-2 text-base font-semibold text-gray-900">{c.titulo}</h4>
              {c.paragrafos.map((p) => (
                <p key={p} className="mb-2">
                  {p}
                </p>
              ))}
              {c.itens && (
                <ul className="mb-2 list-disc space-y-1 pl-5">
                  {c.itens.map((i) => (
                    <li key={i}>{i}</li>
                  ))}
                </ul>
              )}
              {c.tabela && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-500">
                        {c.tabela.colunas.map((col) => (
                          <th key={col} className="p-1.5">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {c.tabela.linhas.map((l) => (
                        <tr key={l[0]} className="border-t border-gray-100 align-top">
                          {l.map((cel, j) => (
                            <td key={j} className="p-1.5">
                              {cel}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </div>
      </Modal>
    </>
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
        <div className="mt-3 flex flex-wrap gap-2">
          <TrajetoriaCompleta />
          <PromptsEMecanica />
        </div>
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

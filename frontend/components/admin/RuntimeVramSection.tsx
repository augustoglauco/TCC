"use client";

function formatVram(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "0 GB";
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

interface RuntimeVramSectionProps {
  keepAlive: string;
  warmupOnStartup: boolean;
  modelLoaded: boolean;
  vramBytes: number | null;
  salvando: boolean;
  acaoVramEmAndamento: "preload" | "unload" | null;
  onKeepAlive: (v: string) => void;
  onWarmup: (v: boolean) => void;
  onCarregar: () => void;
  onLiberar: () => void;
}

export function RuntimeVramSection({
  keepAlive,
  warmupOnStartup,
  modelLoaded,
  vramBytes,
  salvando,
  acaoVramEmAndamento,
  onKeepAlive,
  onWarmup,
  onCarregar,
  onLiberar,
}: RuntimeVramSectionProps) {
  return (
    <div className="space-y-4 pt-4 border-t border-slate-200/80">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🚀</span> Residência na VRAM &amp; Otimização de Latência (Ollama)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Evite latência de cold start mantendo os pesos do modelo local residentes na memória de
            GPU
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${
              modelLoaded
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${modelLoaded ? "bg-emerald-500 animate-pulse" : "bg-slate-400"}`}
            />
            {modelLoaded
              ? `Modelo Carregado na VRAM (${formatVram(vramBytes)})`
              : "Modelo Descarregado (0 GB)"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3 hover:border-slate-300 transition-all flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="rt-keep-alive" className="text-xs font-bold text-slate-800">
                Tempo de Retenção na VRAM (keep_alive)
              </label>
              <span className="text-[10px] font-mono bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-bold">
                Ollama
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Define por quanto tempo o modelo local permanece na memória GPU após responder.
            </p>
          </div>
          <select
            id="rt-keep-alive"
            value={keepAlive}
            onChange={(e) => onKeepAlive(e.target.value)}
            className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-medium text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          >
            <option value="-1">Permanente / Indefinido (-1) — Recomendado (Zero Latência)</option>
            <option value="24h">24 Horas (24h)</option>
            <option value="1h">1 Hora (1h)</option>
            <option value="30m">30 Minutos (30m)</option>
            <option value="15m">15 Minutos (15m)</option>
            <option value="5m">5 Minutos (5m — Padrão do Ollama)</option>
            <option value="0">Descarregar Imediatamente (0) — Economia Máxima de VRAM</option>
          </select>
          <div className="text-[11px] text-slate-500 bg-slate-50 p-2.5 rounded-lg border border-slate-100 flex items-start gap-2">
            <span className="text-sm">💡</span>
            <span>
              Com <strong>Permanente (-1)</strong>, o modelo não é descarregado após 5 minutos de
              inatividade, eliminando a espera de recarga do modelo nas conversas.
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3 hover:border-slate-300 transition-all flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">
                Pré-aquecimento (Warmup) &amp; Controle Manual
              </span>
              <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                Inicialização
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Suba o modelo para a GPU logo no boot do servidor ou faça a gestão manual sob demanda.
            </p>
          </div>

          <label className="flex items-start gap-2.5 cursor-pointer py-1">
            <input
              id="rt-warmup-startup"
              type="checkbox"
              checked={warmupOnStartup}
              onChange={(e) => onWarmup(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <div className="text-xs">
              <span className="font-semibold text-slate-800 block">
                Pré-carregar modelo ao inicializar o backend
              </span>
              <span className="text-slate-500 text-[11px]">
                Dispara uma carga não bloqueante na inicialização para o primeiro usuário ter
                resposta imediata.
              </span>
            </div>
          </label>

          <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
            <button
              type="button"
              onClick={onCarregar}
              disabled={salvando || acaoVramEmAndamento !== null}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 disabled:opacity-50 cursor-pointer transition-colors"
            >
              {acaoVramEmAndamento === "preload" ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Carregando...</span>
                </>
              ) : (
                <>
                  <span>⚡</span>
                  <span>Carregar na GPU</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onLiberar}
              disabled={salvando || acaoVramEmAndamento !== null}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-100 border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 disabled:opacity-50 cursor-pointer transition-colors"
            >
              {acaoVramEmAndamento === "unload" ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-700 border-t-transparent" />
                  <span>Liberando...</span>
                </>
              ) : (
                <>
                  <span>🧹</span>
                  <span>Liberar VRAM</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

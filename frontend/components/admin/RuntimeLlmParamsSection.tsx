"use client";

interface RuntimeLlmParamsSectionProps {
  temperatura: string;
  numCtx: string;
  topP: string;
  topK: string;
  repeatPenalty: string;
  seed: string;
  localTimeout: string;
  externalTimeout: string;
  onTemperatura: (v: string) => void;
  onNumCtx: (v: string) => void;
  onTopP: (v: string) => void;
  onTopK: (v: string) => void;
  onRepeatPenalty: (v: string) => void;
  onSeed: (v: string) => void;
  onLocalTimeout: (v: string) => void;
  onExternalTimeout: (v: string) => void;
}

const inputCls =
  "block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20";

const cardCls =
  "rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all";

interface FieldCardProps {
  id: string;
  label: string;
  badge: string;
  badgeCls: string;
  hint: string;
  children: React.ReactNode;
}

function FieldCard({ id, label, badge, badgeCls, hint, children }: FieldCardProps) {
  return (
    <div className={cardCls}>
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-xs font-bold text-slate-800">
          {label}
        </label>
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${badgeCls}`}>{badge}</span>
      </div>
      {children}
      <p className="text-[11px] text-slate-500 leading-tight">{hint}</p>
    </div>
  );
}

export function RuntimeLlmParamsSection({
  temperatura,
  numCtx,
  topP,
  topK,
  repeatPenalty,
  seed,
  localTimeout,
  externalTimeout,
  onTemperatura,
  onNumCtx,
  onTopP,
  onTopK,
  onRepeatPenalty,
  onSeed,
  onLocalTimeout,
  onExternalTimeout,
}: RuntimeLlmParamsSectionProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>🎛️</span> Parâmetros de Inferência LLM
        </h3>
        <span className="text-xs text-slate-500">Temperatura e limites de tempo de execução</span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <FieldCard
          id="rt-temperature"
          label="Temperatura (temperature)"
          badge="0.0 – 2.0"
          badgeCls="bg-slate-100 text-slate-600"
          hint="Vazio = usa a temperatura padrão do modelo local (ex: 0.7)."
        >
          <input
            id="rt-temperature"
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={temperatura}
            onChange={(e) => onTemperatura(e.target.value)}
            placeholder="Default do modelo"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-num-ctx"
          label="Janela de Contexto (num_ctx)"
          badge="tokens"
          badgeCls="bg-blue-50 text-blue-700 font-bold"
          hint="Tamanho do contexto enviado ao Ollama. Vazio = padrão (geralmente 2048)."
        >
          <input
            id="rt-num-ctx"
            type="number"
            min={256}
            max={131072}
            step={256}
            value={numCtx}
            onChange={(e) => onNumCtx(e.target.value)}
            placeholder="ex: 4096, 8192"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-top-p"
          label="Nucleus Sampling (top_p)"
          badge="0.0 – 1.0"
          badgeCls="bg-slate-100 text-slate-600"
          hint="Corte cumulativo de probabilidade de tokens. Vazio = padrão (0.9)."
        >
          <input
            id="rt-top-p"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={topP}
            onChange={(e) => onTopP(e.target.value)}
            placeholder="ex: 0.9"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-top-k"
          label="Top-K Sampling (top_k)"
          badge="inteiro"
          badgeCls="bg-slate-100 text-slate-600"
          hint="Limita o vocabulário aos K tokens mais prováveis. Vazio = padrão (40)."
        >
          <input
            id="rt-top-k"
            type="number"
            min={1}
            max={200}
            step={1}
            value={topK}
            onChange={(e) => onTopK(e.target.value)}
            placeholder="ex: 40"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-repeat-penalty"
          label="Penalidade Repetição (repeat_penalty)"
          badge="0.0 – 2.0"
          badgeCls="bg-slate-100 text-slate-600"
          hint="Penaliza repetição de termos (>1.0 reduz repetições). Vazio = padrão (1.1)."
        >
          <input
            id="rt-repeat-penalty"
            type="number"
            min={0}
            max={2}
            step={0.05}
            value={repeatPenalty}
            onChange={(e) => onRepeatPenalty(e.target.value)}
            placeholder="ex: 1.1"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-seed"
          label="Semente Aleatória (seed)"
          badge="inteiro"
          badgeCls="bg-slate-100 text-slate-600"
          hint="Semente para determinismo em testes/estudos. Vazio = aleatório."
        >
          <input
            id="rt-seed"
            type="number"
            step={1}
            value={seed}
            onChange={(e) => onSeed(e.target.value)}
            placeholder="ex: 42"
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-local-timeout"
          label="Timeout do modelo local"
          badge="segundos"
          badgeCls="bg-blue-50 text-blue-700 font-bold"
          hint="Tempo limite máximo para respostas da API local do Ollama."
        >
          <input
            id="rt-local-timeout"
            type="number"
            min={0}
            max={300}
            step={1}
            value={localTimeout}
            onChange={(e) => onLocalTimeout(e.target.value)}
            className={inputCls}
          />
        </FieldCard>

        <FieldCard
          id="rt-external-timeout"
          label="Timeout do modelo externo"
          badge="segundos"
          badgeCls="bg-indigo-50 text-indigo-700 font-bold"
          hint="Tempo limite máximo para requisições à API do OpenRouter."
        >
          <input
            id="rt-external-timeout"
            type="number"
            min={0}
            max={300}
            step={1}
            value={externalTimeout}
            onChange={(e) => onExternalTimeout(e.target.value)}
            className={inputCls}
          />
        </FieldCard>
      </div>
    </div>
  );
}

"use client";

type EstoqueMode = "desativado" | "deterministico" | "ia";
type EstoqueLlm = "local" | "externo";

interface RuntimeEstoqueSectionProps {
  mode: EstoqueMode;
  llm: EstoqueLlm;
  onMode: (v: EstoqueMode) => void;
  onLlm: (v: EstoqueLlm) => void;
}

export function RuntimeEstoqueSection({ mode, llm, onMode, onLlm }: RuntimeEstoqueSectionProps) {
  return (
    <div className="space-y-3 pt-4 border-t border-slate-200/80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>📦</span> Agente de Previsão de Estoque (R13)
        </h3>
        <span className="text-xs text-slate-500">
          Avisa o administrador quando prevê falta em até 10 dias
        </span>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-4">
        <div className="space-y-2">
          <label
            htmlFor="rt-estoque-agent-mode"
            className="block text-xs font-bold uppercase tracking-wider text-slate-500"
          >
            Agente ativo
          </label>
          <select
            id="rt-estoque-agent-mode"
            value={mode}
            onChange={(e) => onMode(e.target.value as EstoqueMode)}
            className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="deterministico">
              Determinístico — regra de média de baixa (30 dias)
            </option>
            <option value="ia">IA — um LLM avalia risco e sugere reposição</option>
            <option value="desativado">Desativado</option>
          </select>
        </div>
        {mode === "ia" && (
          <div className="space-y-2 pt-3 border-t border-slate-100">
            <label
              htmlFor="rt-estoque-agent-llm"
              className="block text-xs font-bold uppercase tracking-wider text-slate-500"
            >
              Modelo usado pelo agente de IA
            </label>
            <select
              id="rt-estoque-agent-llm"
              value={llm}
              onChange={(e) => onLlm(e.target.value as EstoqueLlm)}
              className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="local">Modelo local (Ollama)</option>
              <option value="externo">Modelo externo (OpenRouter)</option>
            </select>
            <p className="text-xs text-slate-500 leading-relaxed">
              Se o modelo não responder ou devolver algo inválido, o agente usa a regra
              determinística, então nenhum alerta se perde.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

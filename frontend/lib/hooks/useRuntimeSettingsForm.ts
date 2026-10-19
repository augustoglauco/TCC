import { useEffect, useState } from "react";

import {
  RuntimeSettingsApiError,
  getRuntimeSettings,
  preloadLocalModel,
  unloadLocalModel,
  updateRuntimeSettings,
} from "@/lib/api/runtimeSettings";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { RuntimeSettings, RuntimeSettingsUpdate } from "@/lib/types/runtimeSettings";

/** Estado do formulário de parâmetros de execução: campos numéricos viram
 * string (inputs controlados) e são convertidos de volta em `montarPayload`. */
export interface CamposRuntime {
  temperatura: string;
  numCtx: string;
  topP: string;
  topK: string;
  repeatPenalty: string;
  seed: string;
  localTimeout: string;
  externalTimeout: string;
  ragTopK: string;
  ragScoreThreshold: string;
  ragSearchDomainFallback: boolean;
  routerProvider: "heuristica" | "heuristica_llm" | "jev_openrouter";
  toneMonitorEnabled: boolean;
  toneMonitorProvider: "heuristica_llm" | "jev_openrouter";
  estoqueAgentMode: "desativado" | "deterministico" | "ia";
  estoqueAgentLlm: "local" | "externo";
  externalVisionModel: string;
  imageInternalConfidence: string;
  imageExternalConfidence: string;
  keepAlive: string;
  warmupOnStartup: boolean;
  modelLoaded: boolean;
  vramBytes: number | null;
}

const CAMPOS_INICIAIS: CamposRuntime = {
  temperatura: "",
  numCtx: "",
  topP: "",
  topK: "",
  repeatPenalty: "",
  seed: "",
  localTimeout: "",
  externalTimeout: "",
  ragTopK: "3",
  ragScoreThreshold: "0.35",
  ragSearchDomainFallback: true,
  routerProvider: "heuristica_llm",
  toneMonitorEnabled: true,
  toneMonitorProvider: "heuristica_llm",
  estoqueAgentMode: "deterministico",
  estoqueAgentLlm: "local",
  externalVisionModel: "",
  imageInternalConfidence: "0.30",
  imageExternalConfidence: "0.70",
  keepAlive: "-1",
  warmupOnStartup: true,
  modelLoaded: false,
  vramBytes: null,
};

function strOrEmpty(v: number | null | undefined): string {
  return v === null || v === undefined ? "" : String(v);
}

function strOuPadrao(v: number | null | undefined, padrao: string): string {
  return v != null ? String(v) : padrao;
}

function numOuNull(v: string): number | null {
  return v.trim() === "" ? null : Number(v);
}

function numOuUndefined(v: string): number | undefined {
  return v.trim() === "" ? undefined : Number(v);
}

function camposVram(s: RuntimeSettings): Pick<CamposRuntime, "modelLoaded" | "vramBytes"> {
  return {
    modelLoaded: s.local_model_loaded ?? false,
    vramBytes: s.local_model_vram_bytes ?? null,
  };
}

function camposVramEKeepAlive(
  s: RuntimeSettings,
): Pick<CamposRuntime, "keepAlive" | "warmupOnStartup" | "modelLoaded" | "vramBytes"> {
  return {
    keepAlive: s.local_llm_keep_alive ?? "-1",
    warmupOnStartup: s.local_llm_warmup_on_startup ?? true,
    ...camposVram(s),
  };
}

function camposLlm(s: RuntimeSettings): Partial<CamposRuntime> {
  return {
    temperatura: strOrEmpty(s.local_llm_temperature),
    numCtx: strOrEmpty(s.local_llm_num_ctx),
    topP: strOrEmpty(s.local_llm_top_p),
    topK: strOrEmpty(s.local_llm_top_k),
    repeatPenalty: strOrEmpty(s.local_llm_repeat_penalty),
    seed: strOrEmpty(s.local_llm_seed),
    localTimeout: String(s.local_llm_timeout_s),
    externalTimeout: String(s.external_llm_timeout_s),
  };
}

function camposRagERoteamento(s: RuntimeSettings): Partial<CamposRuntime> {
  return {
    ragTopK: strOuPadrao(s.rag_top_k, "3"),
    ragScoreThreshold: strOuPadrao(s.rag_score_threshold, "0.35"),
    ragSearchDomainFallback: s.rag_search_domain_fallback ?? true,
    routerProvider: s.intent_router_provider ?? "heuristica_llm",
    toneMonitorEnabled: s.tone_monitor_enabled ?? true,
    toneMonitorProvider: s.tone_monitor_provider ?? "heuristica_llm",
    estoqueAgentMode: s.estoque_agent_mode ?? "deterministico",
    estoqueAgentLlm: s.estoque_agent_llm ?? "local",
  };
}

function camposVisao(s: RuntimeSettings): Partial<CamposRuntime> {
  return {
    externalVisionModel: s.external_vision_model_name ?? "",
    imageInternalConfidence: strOuPadrao(s.image_internal_confidence, "0.30"),
    imageExternalConfidence: strOuPadrao(s.image_external_confidence, "0.70"),
  };
}

function camposDeSettings(s: RuntimeSettings): CamposRuntime {
  return {
    ...CAMPOS_INICIAIS,
    ...camposLlm(s),
    ...camposRagERoteamento(s),
    ...camposVisao(s),
    ...camposVramEKeepAlive(s),
  };
}

function montarPayload(c: CamposRuntime): RuntimeSettingsUpdate {
  return {
    local_llm_temperature: numOuNull(c.temperatura),
    local_llm_num_ctx: numOuNull(c.numCtx),
    local_llm_top_p: numOuNull(c.topP),
    local_llm_top_k: numOuNull(c.topK),
    local_llm_repeat_penalty: numOuNull(c.repeatPenalty),
    local_llm_seed: numOuNull(c.seed),
    local_llm_timeout_s: Number(c.localTimeout),
    external_llm_timeout_s: Number(c.externalTimeout),
    rag_top_k: numOuUndefined(c.ragTopK),
    rag_score_threshold: numOuUndefined(c.ragScoreThreshold),
    rag_search_domain_fallback: c.ragSearchDomainFallback,
    intent_router_provider: c.routerProvider,
    tone_monitor_enabled: c.toneMonitorEnabled,
    tone_monitor_provider: c.toneMonitorProvider,
    estoque_agent_mode: c.estoqueAgentMode,
    estoque_agent_llm: c.estoqueAgentLlm,
    external_vision_model_name: c.externalVisionModel.trim() || undefined,
    image_internal_confidence: numOuUndefined(c.imageInternalConfidence),
    image_external_confidence: numOuUndefined(c.imageExternalConfidence),
    local_llm_keep_alive: c.keepAlive,
    local_llm_warmup_on_startup: c.warmupOnStartup,
  };
}

function mensagemErro(err: unknown, fallback: string): string {
  return err instanceof RuntimeSettingsApiError ? err.message : fallback;
}

interface Callbacks {
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

/** Estado e ações do formulário de parâmetros de execução (`/admin/modelos`). */
export function useRuntimeSettingsForm({ onError, onSuccess }: Callbacks) {
  const token = useAuthStore((s) => s.token);
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [campos, setCampos] = useState<CamposRuntime>(CAMPOS_INICIAIS);
  const [acaoVramEmAndamento, setAcaoVramEmAndamento] = useState<"preload" | "unload" | null>(null);
  const [salvando, setSalvando] = useState(false);

  function mesclar(parcial: Partial<CamposRuntime>) {
    setCampos((prev) => ({ ...prev, ...parcial }));
  }

  /** Setter de um campo, no formato `onX={setCampo("x")}` das seções. */
  function setCampo<K extends keyof CamposRuntime>(chave: K) {
    return (valor: CamposRuntime[K]) => mesclar({ [chave]: valor } as Partial<CamposRuntime>);
  }

  useEffect(() => {
    let cancelado = false;
    async function carregar() {
      if (!token) return;
      try {
        const atual = await getRuntimeSettings(token);
        if (cancelado) return;
        setSettings(atual);
        setCampos(camposDeSettings(atual));
      } catch (err) {
        if (!cancelado) {
          onError(mensagemErro(err, "Erro inesperado ao carregar os parâmetros de execução."));
        }
      }
    }
    carregar();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function salvar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (salvando || !token) return;
    setSalvando(true);
    try {
      const atualizado = await updateRuntimeSettings(token, montarPayload(campos));
      setSettings(atualizado);
      mesclar(camposVramEKeepAlive(atualizado));
      onSuccess("Parâmetros de execução aplicados e salvos no banco.");
    } catch (err) {
      onError(mensagemErro(err, "Erro inesperado ao aplicar os parâmetros."));
    } finally {
      setSalvando(false);
    }
  }

  async function acaoVram(
    acao: "preload" | "unload",
    executar: (t: string) => Promise<RuntimeSettings>,
    sucesso: string,
    erro: string,
  ) {
    if (acaoVramEmAndamento || !token) return;
    setAcaoVramEmAndamento(acao);
    try {
      const resp = await executar(token);
      setSettings(resp);
      mesclar(camposVram(resp));
      onSuccess(sucesso);
    } catch (err) {
      onError(mensagemErro(err, erro));
    } finally {
      setAcaoVramEmAndamento(null);
    }
  }

  const carregarVram = () =>
    acaoVram(
      "preload",
      preloadLocalModel,
      "Modelo local carregado na VRAM da GPU com sucesso!",
      "Erro ao tentar carregar modelo na VRAM.",
    );

  const liberarVram = () =>
    acaoVram(
      "unload",
      unloadLocalModel,
      "VRAM liberada com sucesso (modelo descarregado).",
      "Erro ao tentar liberar VRAM.",
    );

  return {
    carregado: settings !== null,
    campos,
    setCampo,
    salvando,
    acaoVramEmAndamento,
    salvar,
    carregarVram,
    liberarVram,
  };
}

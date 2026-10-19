import { useCallback, useEffect, useState } from "react";
import { atualizarFerramenta, fetchFerramentas } from "@/lib/api/ferramentas";
import type { FerramentaStatus } from "@/lib/api/ferramentas";

export interface ResultadoAtualizacao {
  id: string;
  sucesso: boolean;
  saida: string;
}

function mensagemDeErro(err: unknown, padrao: string): string {
  return err instanceof Error ? err.message : padrao;
}

/** Estado e ações da página de ferramentas de código (carregar status, atualizar). */
export function useFerramentas(token: string | null, habilitado: boolean) {
  const [ferramentas, setFerramentas] = useState<FerramentaStatus[] | null>(null);
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [atualizando, setAtualizando] = useState(false);
  const [resultadoAtualizacao, setResultadoAtualizacao] = useState<ResultadoAtualizacao | null>(
    null,
  );

  const carregar = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchFerramentas(token);
      setFerramentas(res.ferramentas);
      setSelecionada((atual) => atual ?? res.ferramentas.find((f) => f.online)?.id ?? null);
    } catch (err: unknown) {
      setError(mensagemDeErro(err, "Erro ao consultar as ferramentas."));
    } finally {
      setLoading(false);
    }
  }, [token]);

  const atualizar = async (id: "graphify" | "gitnexus") => {
    if (!token) return;
    setAtualizando(true);
    setResultadoAtualizacao(null);
    try {
      setResultadoAtualizacao({ id, ...(await atualizarFerramenta(id, token)) });
      await carregar();
    } catch (err: unknown) {
      setResultadoAtualizacao({
        id,
        sucesso: false,
        saida: mensagemDeErro(err, "Erro ao atualizar a ferramenta."),
      });
    } finally {
      setAtualizando(false);
    }
  };

  useEffect(() => {
    if (habilitado && token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregar();
    }
  }, [habilitado, token, carregar]);

  return {
    ferramentas,
    selecionada,
    setSelecionada,
    loading,
    error,
    atualizando,
    resultadoAtualizacao,
    setResultadoAtualizacao,
    carregar,
    atualizar,
  };
}

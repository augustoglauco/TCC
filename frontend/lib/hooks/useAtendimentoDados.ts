import { useCallback, useEffect, useState } from "react";
import {
  fetchDetalhesConversa,
  fetchFilaEspera,
  fetchMeusChats,
  type AtendimentoDetalhes,
  type AtendimentoFilaItem,
} from "@/lib/api/adminAtendimento";

interface Params {
  token: string | null;
  isAdmin: boolean;
  hasHydrated: boolean;
  atendenteId: string;
}

/** Estado e polling da central de atendimento: fila (5s) e detalhes do chat ativo (3s). */
export function useAtendimentoDados({ token, isAdmin, hasHydrated, atendenteId }: Params) {
  const [fila, setFila] = useState<AtendimentoFilaItem[]>([]);
  const [meusChats, setMeusChats] = useState<AtendimentoFilaItem[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [detalhesCarregados, setDetalhesCarregados] = useState<AtendimentoDetalhes | null>(null);
  const [loadingFila, setLoadingFila] = useState(true);

  // Derivado em vez de estado: sem chat ativo nao ha detalhes. Derivar evita o
  // setState sincrono dentro de efeito que a regra react-hooks/set-state-in-effect proibe.
  const detalhes = activeChatId ? detalhesCarregados : null;

  const carregarFilaEMeusChats = useCallback(async () => {
    if (!token || !isAdmin) return;
    try {
      const [filaRes, meusChatsRes] = await Promise.all([
        fetchFilaEspera(token),
        fetchMeusChats(atendenteId, token),
      ]);
      setFila(filaRes);
      setMeusChats(meusChatsRes);

      // Achado de 2026-10-07: este bloco só tinha o comentário da intenção,
      // nunca a limpeza em si — quando o cliente encerrava a conversa (ou
      // outro atendente/a devolvia para a IA), ela sumia da lista de abas
      // (`meusChats`), mas `activeChatId`/`detalhes` continuavam apontando
      // para ela. O painel de chat ativo (`MeusChatsTabs`) não olha o
      // status da conversa para decidir o que mostrar — então o atendente
      // via o chat como se o cliente ainda estivesse ali, podendo mandar
      // mensagem sem efeito, achando que a conversa "não encerra".
      if (activeChatId && !meusChatsRes.some((c) => c.id === activeChatId)) {
        setActiveChatId(null);
        setDetalhesCarregados(null);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erro ao atualizar fila";
      console.error("Erro ao atualizar fila:", message);
    }
  }, [token, isAdmin, atendenteId, activeChatId]);

  // Carrega fila ao montar e estabelece polling a cada 5s
  useEffect(() => {
    if (!hasHydrated || !isAdmin || !token) return;

    // Falso positivo: `carregarFilaEMeusChats` so toca estado depois de
    // `await Promise.all([...])` sobre funcoes `async` importadas, logo nao
    // ha setState sincrono. A regra nao resolve a assincronia de funcoes
    // importadas e assume o pior caso.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarFilaEMeusChats().finally(() => setLoadingFila(false));

    const interval = setInterval(() => {
      void carregarFilaEMeusChats();
    }, 5000);

    return () => clearInterval(interval);
  }, [hasHydrated, isAdmin, token, carregarFilaEMeusChats]);

  // Carrega detalhes do chat ativo e atualiza a cada 3s se ativo
  const carregarDetalhes = useCallback(async () => {
    if (!activeChatId || !token) return;
    try {
      const data = await fetchDetalhesConversa(activeChatId, token);
      setDetalhesCarregados(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erro ao carregar detalhes";
      console.error("Erro ao carregar detalhes:", message);
    }
  }, [activeChatId, token]);

  useEffect(() => {
    if (!activeChatId) return;
    // Falso positivo: `carregarDetalhes` so toca estado depois de
    // `await fetchDetalhesConversa` (funcao `async` importada).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregarDetalhes();
    const interval = setInterval(() => {
      void carregarDetalhes();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeChatId, carregarDetalhes]);

  const limparChatAtivo = useCallback(() => {
    setActiveChatId(null);
    setDetalhesCarregados(null);
  }, []);

  const recarregarFila = useCallback(() => {
    setLoadingFila(true);
    void carregarFilaEMeusChats().finally(() => setLoadingFila(false));
  }, [carregarFilaEMeusChats]);

  return {
    fila,
    meusChats,
    activeChatId,
    setActiveChatId,
    detalhes,
    loadingFila,
    carregarFilaEMeusChats,
    carregarDetalhes,
    limparChatAtivo,
    recarregarFila,
  };
}

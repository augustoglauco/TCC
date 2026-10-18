import { useEffect, useState } from "react";
import { fetchProductById, Produto } from "@/lib/api/products";

const ERRO_ID_INVALIDO = "Identificador de produto inválido.";
const ERRO_PADRAO = "Não foi possível carregar os detalhes do produto.";

interface EstadoProduto {
  product: Produto | null;
  loading: boolean;
  error: string | null;
}

/** Carrega o produto pelo id da rota; ignora respostas de ids já trocados. */
export function useProduto(id: string): EstadoProduto {
  const [state, setState] = useState<EstadoProduto>({ product: null, loading: true, error: null });

  useEffect(() => {
    let isMounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((s) => ({ ...s, loading: true, error: null }));

    const produtoId = Number.parseInt(id, 10);
    if (Number.isNaN(produtoId)) {
      setState((s) => ({ ...s, loading: false, error: ERRO_ID_INVALIDO }));
      return;
    }

    fetchProductById(produtoId)
      .then((product) => {
        if (isMounted) setState({ product, loading: false, error: null });
      })
      .catch((err) => {
        if (isMounted) {
          const error = err instanceof Error ? err.message : ERRO_PADRAO;
          setState((s) => ({ ...s, loading: false, error }));
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id]);

  return state;
}

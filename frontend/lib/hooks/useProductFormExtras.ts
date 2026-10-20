"use client";

import { useCallback, useState } from "react";
import {
  updateAdminProductStock,
  addAdminProductVolumeDiscount,
  deleteAdminProductVolumeDiscount,
  fetchAdminProductCompatibilities,
  addAdminProductCompatibility,
  deleteAdminProductCompatibility,
} from "@/lib/api/adminProducts";
import type {
  AdminProduct,
  AdminProductStock,
  AdminProductVolumeDiscount,
  AdminProductCompatibility,
} from "@/lib/types/adminProducts";
import { mensagemDeErro } from "./useProductFormCampos";

interface ExtrasDeps {
  token: string | null;
  produtoParaEditar?: AdminProduct | null;
  onSuccess: (produtoAtualizado?: AdminProduct) => void;
  setError: (msg: string | null) => void;
}

const descontoValido = (qtdMin: number, perc: number) =>
  !isNaN(qtdMin) && qtdMin > 0 && !isNaN(perc) && perc > 0;

type SetError = (msg: string | null) => void;

async function executarAcao(
  setError: SetError,
  setBusy: (busy: boolean) => void,
  mensagemFalha: string,
  acao: () => Promise<void>,
) {
  setBusy(true);
  setError(null);
  try {
    await acao();
  } catch (err) {
    setError(mensagemDeErro(err, mensagemFalha));
  } finally {
    setBusy(false);
  }
}

function useEstoqueCd({ token, produtoParaEditar, onSuccess, setError }: ExtrasDeps) {
  const [estoques, setEstoques] = useState<AdminProductStock[]>([]);
  const [cdNome, setCdNome] = useState("CD-Matriz");
  const [cdQtd, setCdQtd] = useState("10");
  const [updatingStock, setUpdatingStock] = useState(false);

  const handleSalvarEstoque = async () => {
    if (!produtoParaEditar || !cdNome.trim() || !token) return;
    const qtd = parseInt(cdQtd, 10);
    if (isNaN(qtd) || qtd < 0) {
      setError("Informe uma quantidade válida de estoque.");
      return;
    }
    await executarAcao(setError, setUpdatingStock, "Erro ao atualizar estoque", async () => {
      const prod = await updateAdminProductStock(token, produtoParaEditar.id, cdNome.trim(), qtd);
      setEstoques(prod.estoques || []);
      onSuccess(prod);
    });
  };

  return { estoques, setEstoques, cdNome, setCdNome, cdQtd, setCdQtd, updatingStock, handleSalvarEstoque };
}

function useDescontosVolume({ token, produtoParaEditar, onSuccess, setError }: ExtrasDeps) {
  const [descontosVolume, setDescontosVolume] = useState<AdminProductVolumeDiscount[]>([]);
  const [descQtdMin, setDescQtdMin] = useState("5");
  const [descPercentual, setDescPercentual] = useState("10");
  const [updatingDiscount, setUpdatingDiscount] = useState(false);

  const handleAdicionarDesconto = async () => {
    if (!produtoParaEditar || !token) return;
    const qtdMin = parseInt(descQtdMin, 10);
    const perc = parseFloat(descPercentual);
    if (!descontoValido(qtdMin, perc)) {
      setError("Informe quantidade mínima (>0) e percentual válido (>0).");
      return;
    }
    await executarAcao(setError, setUpdatingDiscount, "Erro ao adicionar faixa de desconto", async () => {
      const prod = await addAdminProductVolumeDiscount(token, produtoParaEditar.id, qtdMin, perc);
      setDescontosVolume(prod.descontos_volume || []);
      onSuccess(prod);
    });
  };

  const handleRemoverDesconto = async (descontoId: string) => {
    if (!produtoParaEditar || !token) return;
    await executarAcao(setError, setUpdatingDiscount, "Erro ao excluir faixa de desconto", async () => {
      const prod = await deleteAdminProductVolumeDiscount(token, produtoParaEditar.id, descontoId);
      setDescontosVolume(prod.descontos_volume || []);
      onSuccess(prod);
    });
  };

  return {
    descontosVolume,
    setDescontosVolume,
    descQtdMin,
    setDescQtdMin,
    descPercentual,
    setDescPercentual,
    updatingDiscount,
    handleAdicionarDesconto,
    handleRemoverDesconto,
  };
}

function useCompatibilidades({ token, produtoParaEditar, setError }: ExtrasDeps) {
  const [compatividades, setCompatividades] = useState<AdminProductCompatibility[]>([]);
  const [compativelSelectedId, setCompativelSelectedId] = useState("");
  const [updatingCompatibility, setUpdatingCompatibility] = useState(false);

  const handleAdicionarCompatibilidade = async () => {
    if (!produtoParaEditar || !compativelSelectedId || !token) return;
    const targetId = parseInt(compativelSelectedId, 10);
    if (isNaN(targetId) || targetId === produtoParaEditar.id) return;
    await executarAcao(setError, setUpdatingCompatibility, "Erro ao adicionar compatibilidade", async () => {
      setCompatividades(await addAdminProductCompatibility(token, produtoParaEditar.id, targetId));
      setCompativelSelectedId("");
    });
  };

  const handleRemoverCompatibilidade = async (compativelComId: number) => {
    if (!produtoParaEditar || !token) return;
    await executarAcao(setError, setUpdatingCompatibility, "Erro ao remover compatibilidade", async () => {
      setCompatividades(
        await deleteAdminProductCompatibility(token, produtoParaEditar.id, compativelComId),
      );
    });
  };

  return {
    compatividades,
    setCompatividades,
    compativelSelectedId,
    setCompativelSelectedId,
    updatingCompatibility,
    handleAdicionarCompatibilidade,
    handleRemoverCompatibilidade,
  };
}

/** Abas de estoque por CD, descontos por volume e compatibilidades (só produto já salvo). */
export function useProductFormExtras(deps: ExtrasDeps) {
  const { setEstoques, ...estoque } = useEstoqueCd(deps);
  const { setDescontosVolume, ...desconto } = useDescontosVolume(deps);
  const { setCompatividades, ...compat } = useCompatibilidades(deps);

  const limpar = useCallback(() => {
    setEstoques([]);
    setDescontosVolume([]);
    setCompatividades([]);
  }, [setEstoques, setDescontosVolume, setCompatividades]);

  const preencher = useCallback(
    (p: AdminProduct, tokenAtual: string | null) => {
      setEstoques(p.estoques || []);
      setDescontosVolume(p.descontos_volume || []);
      if (tokenAtual) {
        fetchAdminProductCompatibilities(tokenAtual, p.id)
          .then(setCompatividades)
          .catch(() => setCompatividades([]));
      }
    },
    [setEstoques, setDescontosVolume, setCompatividades],
  );

  return { ...estoque, ...desconto, ...compat, preencher, limpar };
}

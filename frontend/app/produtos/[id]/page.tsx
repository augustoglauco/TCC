"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import { fetchProductById, Produto } from "@/lib/api/products";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface ProdutoPageProps {
  params: Promise<{ id: string }> | { id: string };
}

export default function ProdutoDetalhePage({ params }: ProdutoPageProps) {
  const resolvedParams = "then" in params ? use(params) : params;
  const { id } = resolvedParams;
  const router = useRouter();

  const [product, setProduct] = useState<Produto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentImgIndex, setCurrentImgIndex] = useState(0);

  // Estado para modal de zoom de imagem
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);

  // Helper para resolver URL completa da imagem
  const resolveImageUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;
    if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) {
      return url;
    }
    const baseUrl = getApiBaseUrl();
    const cleanPath = url.startsWith("/") ? url : `/${url}`;
    return `${baseUrl}${cleanPath}`;
  };

  useEffect(() => {
    let isMounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    const produtoId = Number.parseInt(id, 10);
    if (Number.isNaN(produtoId)) {
      setError("Identificador de produto inválido.");
      setLoading(false);
      return;
    }

    fetchProductById(produtoId)
      .then((data) => {
        if (isMounted) {
          setProduct(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Não foi possível carregar os detalhes do produto.",
          );
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id]);

  // Lista consolidada de imagens do produto
  const imageList = useMemo(() => {
    if (!product) return [];
    const urls: string[] = [];
    if (product.imagens && product.imagens.length > 0) {
      product.imagens.forEach((img) => {
        const full = resolveImageUrl(img.imagem_url);
        if (full && !urls.includes(full)) {
          urls.push(full);
        }
      });
    }
    const mainFull = resolveImageUrl(product.imagem_url);
    if (mainFull && !urls.includes(mainFull)) {
      urls.unshift(mainFull);
    }
    return urls;
  }, [product]);

  // Estoque total somado
  const totalEstoque = useMemo(() => {
    if (!product || !product.estoques || product.estoques.length === 0) return 0;
    return product.estoques.reduce(
      (acc, est) => acc + (est.quantidade > 0 ? est.quantidade : 0),
      0,
    );
  }, [product]);

  const emEstoque = totalEstoque > 0;

  const valorFormatado = (val: number) => {
    const numStr = val.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `R$ ${numStr}`;
  };

  const handleBuy = () => {
    if (!product) return;
    const cd =
      product.estoques && product.estoques.length > 0
        ? product.estoques.find((e) => e.quantidade > 0)?.centro_distribuicao ||
          product.estoques[0].centro_distribuicao
        : "CD-SP";

    const precoEfetivo = product.preco_promocional || product.preco;

    useCartStore.getState().addItem({
      produtoId: product.id,
      nome: product.nome,
      preco: Number(precoEfetivo),
      imagemUrl: product.imagem_url,
      quantidade: 1,
      centroDistribuicao: cd,
    });

    router.push("/pedidos");
  };

  const handleQuote = () => {
    useChatStore.getState().open();
  };

  const activeImageUrl = imageList[currentImgIndex] || null;

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:py-14 animate-pulse">
        <div className="h-4 w-36 bg-slate-200 rounded mb-8" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
          <div className="aspect-4/3 w-full bg-slate-200 rounded-2xl" />
          <div className="space-y-4">
            <div className="h-5 w-24 bg-slate-200 rounded" />
            <div className="h-8 w-3/4 bg-slate-200 rounded" />
            <div className="h-6 w-32 bg-slate-200 rounded" />
            <div className="h-20 w-full bg-slate-200 rounded" />
            <div className="h-12 w-full bg-slate-200 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 text-3xl font-bold mb-4">
          ⚠️
        </div>
        <h1 className="text-2xl font-bold text-slate-900">
          {error?.includes("não encontrado")
            ? "Produto não encontrado"
            : "Erro ao carregar produto"}
        </h1>
        <p className="mt-2 text-sm text-slate-600 max-w-md mx-auto">
          {error || "O produto solicitado não foi localizado no catálogo da empresa."}
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <Link
            href="/produtos"
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            ← Voltar ao Catálogo
          </Link>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
      {/* Breadcrumb e Retorno */}
      <nav
        aria-label="Navegação estrutural"
        className="mb-6 flex items-center gap-2 text-xs sm:text-sm text-slate-500"
      >
        <Link href="/produtos" className="hover:text-blue-600 transition-colors font-medium">
          ← Catálogo de Produtos
        </Link>
        <span>/</span>
        <span className="text-slate-600 font-medium">{product.categoria}</span>
        <span>/</span>
        <span className="text-slate-900 font-semibold truncate max-w-xs">{product.nome}</span>
      </nav>

      {/* Grid Principal: Imagens + Informações Comerciais */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12">
        {/* Coluna da Esquerda: Galeria de Imagens */}
        <div className="space-y-4">
          <div className="relative aspect-4/3 w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-4 flex items-center justify-center shadow-xs group">
            {activeImageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={activeImageUrl}
                alt={product.nome}
                className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105 cursor-pointer"
                onClick={() => setZoomImageUrl(activeImageUrl)}
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-slate-400 p-8 text-center">
                <svg
                  className="h-16 w-16 text-slate-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                <span className="mt-2 text-xs text-slate-400">Sem foto disponível</span>
              </div>
            )}

            {/* Botão de Zoom */}
            {activeImageUrl && (
              <button
                type="button"
                onClick={() => setZoomImageUrl(activeImageUrl)}
                className="absolute top-3 right-3 rounded-full bg-slate-900/60 p-2 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-900 cursor-pointer"
                title="Ampliar imagem (Zoom)"
                aria-label="Ampliar imagem"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
                  />
                </svg>
              </button>
            )}

            {/* Setas de navegação */}
            {imageList.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={() =>
                    setCurrentImgIndex((prev) => (prev === 0 ? imageList.length - 1 : prev - 1))
                  }
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1.5 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
                  aria-label="Imagem anterior"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setCurrentImgIndex((prev) => (prev === imageList.length - 1 ? 0 : prev + 1))
                  }
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1.5 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
                  aria-label="Próxima imagem"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </button>
              </>
            )}
          </div>

          {/* Miniaturas de Fotos */}
          {imageList.length > 1 && (
            <div className="flex gap-2.5 overflow-x-auto pb-2">
              {imageList.map((url, idx) => (
                <button
                  type="button"
                  key={url}
                  onClick={() => setCurrentImgIndex(idx)}
                  className={`relative h-18 w-18 shrink-0 overflow-hidden rounded-xl border p-1 transition-all cursor-pointer ${
                    currentImgIndex === idx
                      ? "border-blue-600 ring-2 ring-blue-600/30"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                  aria-label={`Ver foto ${idx + 1}`}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url}
                    alt={`Foto ${idx + 1}`}
                    className="h-full w-full object-contain rounded-lg"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Coluna da Direita: Dados Comerciais & Ações */}
        <div className="flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            {/* Categoria e Badge de Estoque */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {product.categoria}
              </span>

              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                  emEstoque
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${emEstoque ? "bg-emerald-500" : "bg-amber-500"}`}
                />
                {emEstoque ? `Em estoque (${totalEstoque} un)` : "Sem estoque no momento"}
              </span>
            </div>

            {/* Título */}
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 leading-tight">
              {product.nome}
            </h1>

            {/* Descrição Resumida */}
            {product.descricao && (
              <p className="text-sm text-slate-600 leading-relaxed">{product.descricao}</p>
            )}

            {/* Preço de Venda */}
            <div className="pt-2">
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
                Preço Unitário
              </span>
              <div className="flex items-baseline gap-3">
                {product.preco_promocional ? (
                  <>
                    <span className="text-3xl font-extrabold text-blue-700">
                      {valorFormatado(product.preco_promocional)}
                    </span>
                    <span className="text-sm text-slate-400 line-through">
                      {valorFormatado(product.preco)}
                    </span>
                    <span className="rounded-md bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 text-xs font-bold">
                      Oferta Especial
                    </span>
                  </>
                ) : (
                  <span className="text-3xl font-extrabold text-blue-700">
                    {valorFormatado(product.preco)}
                  </span>
                )}
              </div>
            </div>

            {/* Botões de Ação */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={handleBuy}
                disabled={!emEstoque}
                className={`flex items-center justify-center gap-2 rounded-xl py-3 px-4 text-sm font-bold shadow-xs transition-all cursor-pointer ${
                  emEstoque
                    ? "bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow"
                    : "bg-slate-200 text-slate-400 cursor-not-allowed"
                }`}
              >
                <span>🛒</span>
                <span>Comprar Agora</span>
              </button>

              <button
                type="button"
                onClick={handleQuote}
                className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white py-3 px-4 text-sm font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors shadow-xs cursor-pointer"
              >
                <span>💬</span>
                <span>Cotar com Assistente</span>
              </button>
            </div>
          </div>

          {/* Estoque por Centro de Distribuição */}
          <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 space-y-2.5">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <span>📍</span> Disponibilidade por Centro de Distribuição
            </h2>
            {product.estoques && product.estoques.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {product.estoques.map((est) => (
                  <div
                    key={est.id}
                    className="rounded-xl border border-slate-200 bg-white p-2.5 text-xs shadow-2xs"
                  >
                    <span className="block font-semibold text-slate-700 truncate">
                      {est.centro_distribuicao}
                    </span>
                    <span
                      className={`block font-bold mt-0.5 ${
                        est.quantidade > 0 ? "text-emerald-700" : "text-slate-400"
                      }`}
                    >
                      {est.quantidade > 0 ? `${est.quantidade} un` : "Esgotado"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">Nenhum estoque registrado para este item.</p>
            )}
          </div>

          {/* Faixas de Desconto por Volume (se houver) */}
          {product.descontos_volume && product.descontos_volume.length > 0 && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-4 space-y-2">
              <h2 className="text-xs font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
                <span>🏷️</span> Tabela de Descontos Progressivos
              </h2>
              <div className="flex flex-wrap gap-2">
                {product.descontos_volume.map((desc) => (
                  <span
                    key={desc.id}
                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2.5 py-1 text-xs font-semibold text-blue-800"
                  >
                    A partir de {desc.quantidade_minima} un:{" "}
                    <strong className="text-blue-600">
                      {Number(desc.percentual_desconto)}% OFF
                    </strong>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Seção Inferior: Ficha Técnica & Especificações */}
      <div className="mt-12 pt-8 border-t border-slate-200">
        <h2 className="text-xl font-bold text-slate-900 mb-6">
          Especificações e Detalhes Técnicos
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Coluna 1 e 2: Especificações Técnicas */}
          <div className="md:col-span-2 rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
              Ficha Técnica do Fabricante
            </h3>
            {product.especificacoes_tecnicas ? (
              <div className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
                {product.especificacoes_tecnicas}
              </div>
            ) : (
              <p className="text-sm text-slate-400 italic">
                Especificações detalhadas não cadastradas para este produto.
              </p>
            )}
          </div>

          {/* Coluna 3: Dimensões, Peso e Metadados */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
              Medidas e Propriedades
            </h3>

            <div className="space-y-3 text-xs sm:text-sm">
              <div className="flex justify-between border-b border-slate-100 pb-2">
                <span className="text-slate-500">Dimensões (L x A x P):</span>
                <span className="font-semibold text-slate-900">
                  {product.dimensoes_cm ? `${product.dimensoes_cm} cm` : "Não informado"}
                </span>
              </div>

              <div className="flex justify-between border-b border-slate-100 pb-2">
                <span className="text-slate-500">Peso Estimado:</span>
                <span className="font-semibold text-slate-900">
                  {product.peso_kg ? `${product.peso_kg} kg` : "Não informado"}
                </span>
              </div>

              <div className="flex justify-between border-b border-slate-100 pb-2">
                <span className="text-slate-500">Código do Produto:</span>
                <span className="font-mono font-semibold text-slate-900">#{product.id}</span>
              </div>

              <div className="flex justify-between">
                <span className="text-slate-500">Categoria:</span>
                <span className="font-semibold text-slate-900">{product.categoria}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Modal de Zoom da Imagem */}
      {zoomImageUrl && (
        <ImageZoomModal
          imageUrl={zoomImageUrl}
          productName={product.nome}
          onClose={() => setZoomImageUrl(null)}
        />
      )}
    </div>
  );
}

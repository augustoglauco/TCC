"use client";

import { use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchProductById, Produto } from "@/lib/api/products";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";
import { ProdutoImageGallery } from "./ProdutoImageGallery";
import { ProdutoInfoPanel } from "./ProdutoInfoPanel";
import { ProdutoFichaTecnica } from "./ProdutoFichaTecnica";
import { ProdutoLoadingSkeleton } from "./ProdutoLoadingSkeleton";
import { ProdutoErrorState } from "./ProdutoErrorState";

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
      imagemUrl: resolveImageUrl(product.imagem_url),
      quantidade: 1,
      centroDistribuicao: cd,
    });

    router.push("/pedidos");
  };

  const handleQuote = () => {
    useChatStore.getState().open();
  };

  if (loading) return <ProdutoLoadingSkeleton />;

  if (error || !product) return <ProdutoErrorState error={error} />;
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
        <ProdutoImageGallery
          imageList={imageList}
          currentImgIndex={currentImgIndex}
          productName={product.nome}
          onSelectIndex={setCurrentImgIndex}
          onZoom={setZoomImageUrl}
        />

        <ProdutoInfoPanel
          product={product}
          emEstoque={emEstoque}
          totalEstoque={totalEstoque}
          onBuy={handleBuy}
          onQuote={handleQuote}
        />
      </div>

      <ProdutoFichaTecnica product={product} />

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

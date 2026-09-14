interface ProdutoPageProps {
  params: Promise<{ id: string }>;
}

// MVP: página stub, sem chamada à API de produtos ainda (ver docs/ROADMAP.md, Fase 7).
export default async function ProdutoDetalhePage({ params }: ProdutoPageProps) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Produto {id}</h1>
      <p className="mt-4 text-gray-600">Detalhe do produto em construção.</p>
    </div>
  );
}

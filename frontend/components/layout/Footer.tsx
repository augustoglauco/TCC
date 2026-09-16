import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-gray-500">
        <p>
          Empresa Fictícia TCC — projeto acadêmico de assistente virtual multimodal. Conteúdo
          institucional é ilustrativo.
        </p>
        {/* MVP: links discretos para páginas internas administrativas — não
            entram no menu principal (docs/FRONTEND.md §8), só facilitam
            achá-las durante a demonstração do TCC. */}
        <p className="mt-2 space-x-4">
          <Link href="/admin/ingestao" className="text-gray-400 hover:text-gray-600">
            Admin: ingestão de documentos (RAG)
          </Link>
          <Link href="/admin/modelos" className="text-gray-400 hover:text-gray-600">
            Admin: modelos locais
          </Link>
        </p>
      </div>
    </footer>
  );
}

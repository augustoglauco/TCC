import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-white">
      <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-gray-500">
        <p>
          Empresa Fictícia TCC — projeto acadêmico de assistente virtual multimodal. Conteúdo
          institucional é ilustrativo.
        </p>
        {/* MVP: link discreto para a página interna de ingestão do RAG — não
            entra no menu principal (docs/FRONTEND.md §8), só facilita achá-la
            durante a demonstração do TCC. */}
        <p className="mt-2">
          <Link href="/admin/ingestao" className="text-gray-400 hover:text-gray-600">
            Admin: ingestão de documentos (RAG)
          </Link>
        </p>
      </div>
    </footer>
  );
}

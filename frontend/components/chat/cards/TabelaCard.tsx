import type { ChatCardTabela } from "@/lib/types/chat";

export default function TabelaCard({ card }: { card: ChatCardTabela }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {card.colunas.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {card.linhas.map((linha, i) => (
            <tr key={i}>
              {linha.map((valor, j) => (
                <td key={j} className="px-3 py-2 text-slate-800">
                  {valor === null ? "—" : String(valor)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {card.truncado && (
        <p className="px-3 py-2 text-xs text-slate-500">Mostrando as primeiras 50 linhas.</p>
      )}
    </div>
  );
}

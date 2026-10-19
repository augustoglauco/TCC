import { Tooltip } from "@/components/ui/Tooltip";
import type { CollectionCreatePayload, CollectionPurpose } from "@/lib/types/rag";

const NOME_PURPOSE: Record<CollectionPurpose, string> = {
  chat: "Chat",
  mcp_b2b: "MCP B2B",
  admin: "Admin",
};

function FinalidadeAviso({ purpose }: { purpose: CollectionPurpose }) {
  if (purpose === "mcp_b2b") {
    return (
      <p className="mt-1 text-xs text-amber-700">
        Conteúdo restrito aos revendedores parceiros; consultado pelo canal MCP B2B e pelo Admin no
        modo admin. Pode ser definida como a collection ativa para MCP B2B.
      </p>
    );
  }
  if (purpose === "admin") {
    return (
      <p className="mt-1 text-xs text-amber-700">
        Conteúdo exclusivo do painel de administração — só o Admin o vê quando autenticado. Pode ser
        definida como a collection ativa para Admin.
      </p>
    );
  }
  return (
    <p className="mt-1 text-xs text-blue-700">
      Conteúdo público consultado pelo assistente do chat aberto aos clientes. Pode ser definida
      como a collection ativa para o Chat.
    </p>
  );
}

export function CollectionNameField({
  name,
  onName,
}: {
  name: string;
  onName: (v: string) => void;
}) {
  return (
    <div>
      <div className="flex items-center">
        <label htmlFor="collection-name" className="text-sm font-medium text-gray-900">
          Nome
        </label>
        <Tooltip content="Nome único identificador da collection no Qdrant (ex.: vendas_docs, suporte_manuais)." />
      </div>
      <input
        id="collection-name"
        value={name}
        onChange={(e) => onName(e.target.value)}
        required
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
      />
    </div>
  );
}

export function CollectionPurposeField({
  purpose,
  ativarAposCriar,
  onPurpose,
  onAtivarAposCriar,
}: {
  purpose: CollectionPurpose;
  ativarAposCriar: boolean;
  onPurpose: (v: CollectionPurpose) => void;
  onAtivarAposCriar: (v: boolean) => void;
}) {
  return (
    <div>
      <div className="flex items-center">
        <label htmlFor="collection-purpose" className="text-sm font-medium text-gray-900">
          Finalidade
        </label>
        <Tooltip content="Cada canal possui sua própria collection ativa independente. Chat (pública) para o assistente aberto; MCP B2B para integração com revendedores; Admin para o painel seguro." />
      </div>
      <select
        id="collection-purpose"
        value={purpose}
        onChange={(e) => onPurpose(e.target.value as CollectionPurpose)}
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
      >
        <option value="chat">Chat (pública)</option>
        <option value="mcp_b2b">Restrita ao MCP B2B</option>
        <option value="admin">Exclusiva do Admin</option>
      </select>
      <FinalidadeAviso purpose={purpose} />

      <div className="mt-2.5 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-2.5">
        <input
          id="ativar-apos-criar"
          type="checkbox"
          checked={ativarAposCriar}
          onChange={(e) => onAtivarAposCriar(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
        />
        <label
          htmlFor="ativar-apos-criar"
          className="text-xs font-semibold text-slate-800 cursor-pointer"
        >
          Tornar esta collection a ativa imediata para {NOME_PURPOSE[purpose]}
        </label>
      </div>
    </div>
  );
}

export function CollectionDistanceField({
  value,
  onChange,
}: {
  value: CollectionCreatePayload["distance_metric"];
  onChange: (v: CollectionCreatePayload["distance_metric"]) => void;
}) {
  return (
    <div>
      <div className="flex items-center">
        <label htmlFor="distance-metric" className="text-sm font-medium text-gray-900">
          Métrica de distância
        </label>
        <Tooltip content="Métrica matemática para calcular a similaridade entre vetores. Cosine (cosseno) é ideal para busca semântica em texto." />
      </div>
      <select
        id="distance-metric"
        value={value}
        onChange={(e) => onChange(e.target.value as CollectionCreatePayload["distance_metric"])}
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
      >
        <option value="cosine">Cosine</option>
        <option value="euclid">Euclid</option>
        <option value="dot">Dot</option>
        <option value="manhattan">Manhattan</option>
      </select>
    </div>
  );
}

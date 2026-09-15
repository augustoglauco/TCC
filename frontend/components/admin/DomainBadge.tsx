import type { RagDomain } from "@/lib/types/rag";

const DOMAIN_STYLES: Record<RagDomain, string> = {
  vendas: "bg-blue-100 text-blue-800",
  suporte: "bg-amber-100 text-amber-800",
  atendimento: "bg-purple-100 text-purple-800",
};

const DOMAIN_LABELS: Record<RagDomain, string> = {
  vendas: "Vendas",
  suporte: "Suporte Técnico",
  atendimento: "Atendimento ao Usuário",
};

export function DomainBadge({ domain }: { domain: RagDomain }) {
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${DOMAIN_STYLES[domain]}`}>
      {DOMAIN_LABELS[domain]}
    </span>
  );
}

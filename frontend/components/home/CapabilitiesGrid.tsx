import Link from "next/link";

interface Capability {
  icon: string;
  title: string;
  subtitle: string;
  description: string;
  features: string[];
  href: string;
}

const CAPABILITIES: Capability[] = [
  {
    icon: "👤",
    title: "Controle de Acesso",
    subtitle: "Facial & Biometria",
    description:
      "Terminais de alta tecnologia com reconhecimento facial 3D, biometria digital e leitor de cartões RFID para máxima segurança de ambientes corporativos.",
    features: ["Validação sem contato", "Anti-fraude com IA", "Gestão em rede TCP/IP"],
    href: "/produtos",
  },
  {
    icon: "🛡️",
    title: "Bloqueios & Catracas",
    subtitle: "Aço Inox & Torniquetes",
    description:
      "Sistemas físicos de retenção e liberação de fluxo com mecanismo silencioso, amortecimento suave e design industrial em aço inox escovado.",
    features: ["Aço inox 304", "Braços escamoteáveis", "Passagem acessível PCD"],
    href: "/produtos",
  },
  {
    icon: "⏱️",
    title: "Ponto Eletrônico",
    subtitle: "Portaria 671 MTE",
    description:
      "Registradores eletrônicos de ponto certificados e aderentes às normas vigentes, com comprovante impresso térmico e integração em nuvem.",
    features: ["100% legalizado MTE", "Guilhotina integrada", "Sincronização em nuvem"],
    href: "/produtos",
  },
  {
    icon: "🤖",
    title: "Automação & Protocolo MCP",
    subtitle: "Assistente IA & B2B",
    description:
      "Integração do catálogo e estoque com parceiros via Model Context Protocol (MCP) e agendamento automatizado integrado ao Google Calendar.",
    features: [
      "Consulta de estoque em tempo real",
      "Cotação automatizada",
      "Visitas no Google Calendar",
    ],
    href: "/suporte",
  },
];

export default function CapabilitiesGrid() {
  return (
    <section className="space-y-6 py-6 sm:py-10">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-widest text-blue-600">
            Nossos Domínios
          </span>
          <h2 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 mt-1">
            Soluções Integradas de{" "}
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              Segurança e Gestão
            </span>
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-slate-500 max-w-md">
          Engenharia de precisão e inteligência artificial aplicadas à proteção de ativos, fluxo de
          pessoas e gestão de ponto.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {CAPABILITIES.map((cap) => (
          <Link
            key={cap.title}
            href={cap.href}
            className="group flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm hover:shadow-xl hover:border-blue-400 hover:-translate-y-2 transition-all duration-300 relative overflow-hidden"
          >
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-2xl group-hover:bg-blue-600 group-hover:scale-110 transition-all duration-300">
                <span>{cap.icon}</span>
              </div>

              <div className="mt-5 space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
                  {cap.subtitle}
                </span>
                <h3 className="text-lg font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                  {cap.title}
                </h3>
              </div>

              <p className="mt-2.5 text-xs text-slate-600 leading-relaxed">{cap.description}</p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100 space-y-2">
              {cap.features.map((feat) => (
                <div key={feat} className="flex items-center gap-2 text-[11px] text-slate-500">
                  <span className="h-1 w-1 rounded-full bg-blue-500" />
                  <span>{feat}</span>
                </div>
              ))}

              <div className="pt-2 flex items-center justify-between text-xs font-bold text-blue-600 group-hover:translate-x-1 transition-transform">
                <span>Conhecer Solução</span>
                <span>›</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

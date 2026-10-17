export default function TechMarquee() {
  const ITEMS = [
    "Reconhecimento Facial 3D",
    "Catracas em Inox Escovado",
    "Homologado Portaria 671 MTE",
    "Leitores RFID & UHF Veicular",
    "Fechaduras Digitais Corporativas",
    "Protocolo B2B MCP",
    "Assistente IA Multimodal",
    "Validação Biométrica em 0.2s",
  ];

  return (
    <div className="relative overflow-hidden border-y border-slate-800/80 bg-slate-950 py-3.5 select-none">
      <div className="flex w-max animate-[marquee_25s_linear_infinite] items-center gap-8">
        {[...ITEMS, ...ITEMS].map((item, idx) => (
          <div key={`${item}-${idx}`} className="flex items-center gap-3">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 shadow-sm shadow-blue-400" />
            <span className="text-xs font-bold uppercase tracking-widest text-slate-400 hover:text-slate-200 transition-colors">
              {item}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

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
    <div className="running-text relative overflow-hidden border-y border-white/10 bg-[#14161b] py-5 select-none shadow-lg">
      <div className="flex w-max animate-[marquee_28s_linear_infinite] items-center gap-10">
        {[...ITEMS, ...ITEMS].map((item, idx) => (
          <div key={`${item}-${idx}`} className="flex items-center gap-4">
            <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd] shadow-[0_0_12px_#16c0dd]" />
            <span className="text-sm sm:text-base font-extrabold uppercase tracking-[0.2em] text-white/85 hover:text-[#16c0dd] transition-colors">
              {item}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

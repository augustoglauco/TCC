interface TipoArquivo {
  rotulo: string;
  nome: string;
  cor: string;
}

const TIPOS: Record<string, TipoArquivo> = {
  pdf: { rotulo: "PDF", nome: "Arquivo PDF", cor: "#dc2626" },
  md: { rotulo: "MD", nome: "Arquivo Markdown", cor: "#4f46e5" },
  txt: { rotulo: "TXT", nome: "Arquivo de texto", cor: "#64748b" },
  csv: { rotulo: "CSV", nome: "Arquivo CSV", cor: "#16a34a" },
};

const TIPO_GENERICO: TipoArquivo = { rotulo: "ARQ", nome: "Arquivo", cor: "#2563eb" };

function tipoDoArquivo(filename: string): TipoArquivo {
  const ponto = filename.lastIndexOf(".");
  if (ponto < 0) return TIPO_GENERICO;
  return TIPOS[filename.slice(ponto + 1).toLowerCase()] ?? TIPO_GENERICO;
}

/** Ícone de folha com a "orelha" dobrada e uma etiqueta colorida do tipo do arquivo
 * (PDF, Markdown, texto, CSV; qualquer outro vira o ícone genérico). */
export function FileTypeIcon({
  filename,
  className = "h-12 w-10",
}: {
  filename: string;
  className?: string;
}) {
  const tipo = tipoDoArquivo(filename);

  return (
    <svg
      role="img"
      aria-label={tipo.nome}
      viewBox="0 0 40 48"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M6 2h20l10 10v32a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"
        fill="#ffffff"
        stroke={tipo.cor}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M26 2v8a2 2 0 0 0 2 2h8"
        fill={tipo.cor}
        fillOpacity="0.15"
        stroke={tipo.cor}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M10 18h12M10 22h18"
        stroke={tipo.cor}
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.35"
      />
      <rect x="2" y="29" width="26" height="12" rx="3" fill={tipo.cor} />
      <text
        x="15"
        y="38"
        textAnchor="middle"
        fontSize="8.5"
        fontWeight="700"
        fontFamily="system-ui, sans-serif"
        fill="#ffffff"
        aria-hidden="true"
      >
        {tipo.rotulo}
      </text>
    </svg>
  );
}

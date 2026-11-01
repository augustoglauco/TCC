import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TabelaCard from "@/components/chat/cards/TabelaCard";

describe("TabelaCard", () => {
  it("mostra colunas e linhas e avisa quando o resultado foi truncado", () => {
    render(
      <TabelaCard
        card={{
          tipo: "tabela",
          titulo: "Produtos",
          colunas: ["nome", "preco"],
          linhas: [["iDFace", 1356.3]],
          truncado: true,
        }}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "nome" })).toBeInTheDocument();
    expect(screen.getByText("iDFace")).toBeInTheDocument();
    expect(screen.getByText(/primeiras 50 linhas/i)).toBeInTheDocument();
  });

  it("mostra JSON, booleano e nulo legíveis em vez de [object Object]", () => {
    render(
      <TabelaCard
        card={{
          tipo: "tabela",
          titulo: "Pareceres",
          colunas: ["parecer", "ativo", "obs"],
          linhas: [[{ nota: 5 }, true, null]],
        }}
      />,
    );
    expect(screen.getByText('{"nota":5}')).toBeInTheDocument();
    expect(screen.getByText("true")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
  });
});

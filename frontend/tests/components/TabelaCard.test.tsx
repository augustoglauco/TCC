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
});

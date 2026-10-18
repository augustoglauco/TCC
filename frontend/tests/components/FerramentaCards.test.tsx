import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FerramentaCards } from "@/components/admin/ferramentas/FerramentaCards";
import type { FerramentaStatus } from "@/lib/api/ferramentas";

function ferramenta(over: Partial<FerramentaStatus> = {}): FerramentaStatus {
  return {
    id: "graphify",
    nome: "Graphify",
    descricao: "Grafo estrutural por AST.",
    tipo: "artefato",
    url: "/api/admin/ferramentas/graphify/grafo",
    online: true,
    detalhe: "/repo/graphify-out/graph.html (3.0 MB)",
    comando: "graphify update .",
    ...over,
  };
}

const FERRAMENTAS: FerramentaStatus[] = [
  ferramenta(),
  ferramenta({
    id: "repowise",
    nome: "Repowise",
    descricao: "Wiki viva do código.",
    tipo: "servidor",
    url: "http://localhost:3002",
    online: false,
    detalhe: null,
    comando: "repowise serve",
  }),
  ferramenta({
    id: "gitnexus",
    nome: "GitNexus",
    descricao: "Grafo de chamadas.",
    tipo: "servidor",
    url: "http://localhost:4747",
    online: true,
    detalhe: "HTTP 200",
    comando: "node .gitnexus/run.cjs serve",
  }),
];

describe("FerramentaCards", () => {
  it("renderiza um botão por ferramenta", () => {
    render(
      <FerramentaCards ferramentas={FERRAMENTAS} selecionada={null} onSelecionar={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /Graphify/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Repowise/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /GitNexus/ })).toBeInTheDocument();
  });

  it("marca aria-pressed=true apenas no botão selecionado", () => {
    render(
      <FerramentaCards
        ferramentas={FERRAMENTAS}
        selecionada="repowise"
        onSelecionar={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /Repowise/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /Graphify/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("chama onSelecionar com o id correto ao clicar", () => {
    const onSelecionar = vi.fn();
    render(
      <FerramentaCards
        ferramentas={FERRAMENTAS}
        selecionada={null}
        onSelecionar={onSelecionar}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /GitNexus/ }));
    expect(onSelecionar).toHaveBeenCalledOnce();
    expect(onSelecionar).toHaveBeenCalledWith("gitnexus");
  });

  it("exibe LED Online para ferramenta online e Offline para offline", () => {
    render(
      <FerramentaCards ferramentas={FERRAMENTAS} selecionada={null} onSelecionar={vi.fn()} />,
    );
    const leds = screen.getAllByRole("img");
    const labels = leds.map((el) => el.getAttribute("aria-label"));
    expect(labels).toContain("Online");
    expect(labels).toContain("Offline");
  });

  it("exibe selo 'Gerado' para artefato online e 'Não gerado' para artefato offline", () => {
    render(
      <FerramentaCards
        ferramentas={[
          ferramenta({ tipo: "artefato", online: true }),
          ferramenta({ id: "x", nome: "X", tipo: "artefato", online: false }),
        ]}
        selecionada={null}
        onSelecionar={vi.fn()}
      />,
    );
    expect(screen.getByText("Gerado")).toBeInTheDocument();
    expect(screen.getByText("Não gerado")).toBeInTheDocument();
  });

  it("exibe selo 'No ar' para servidor online e 'Fora do ar' para servidor offline", () => {
    render(
      <FerramentaCards
        ferramentas={[
          ferramenta({ id: "a", nome: "A", tipo: "servidor", online: true }),
          ferramenta({ id: "b", nome: "B", tipo: "servidor", online: false }),
        ]}
        selecionada={null}
        onSelecionar={vi.fn()}
      />,
    );
    expect(screen.getByText("No ar")).toBeInTheDocument();
    expect(screen.getByText("Fora do ar")).toBeInTheDocument();
  });

  it("mostra o comando apenas para ferramentas offline", () => {
    render(
      <FerramentaCards ferramentas={FERRAMENTAS} selecionada={null} onSelecionar={vi.fn()} />,
    );
    // Repowise está offline — comando deve aparecer
    expect(screen.getByText("repowise serve")).toBeInTheDocument();
    // Graphify está online — comando não deve aparecer
    expect(screen.queryByText("graphify update .")).not.toBeInTheDocument();
  });

  it("exibe o detalhe quando presente", () => {
    render(
      <FerramentaCards
        ferramentas={[ferramenta({ detalhe: "/repo/graph.html (3.0 MB)" })]}
        selecionada={null}
        onSelecionar={vi.fn()}
      />,
    );
    expect(screen.getByText("/repo/graph.html (3.0 MB)")).toBeInTheDocument();
  });

  it("usa ícone padrão 🔧 para id desconhecido", () => {
    render(
      <FerramentaCards
        ferramentas={[ferramenta({ id: "desconhecido", nome: "Nova" })]}
        selecionada={null}
        onSelecionar={vi.fn()}
      />,
    );
    expect(screen.getByText("🔧")).toBeInTheDocument();
  });
});

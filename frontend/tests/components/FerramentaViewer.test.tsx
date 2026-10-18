import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FerramentaViewer } from "@/components/admin/ferramentas/FerramentaViewer";
import type { FerramentaStatus } from "@/lib/api/ferramentas";

function ferramenta(over: Partial<FerramentaStatus> = {}): FerramentaStatus {
  return {
    id: "graphify",
    nome: "Graphify",
    descricao: "Grafo estrutural por AST.",
    tipo: "artefato",
    url: "/api/admin/ferramentas/graphify/grafo",
    online: true,
    detalhe: null,
    comando: "graphify update .",
    ...over,
  };
}

const BASE_PROPS = {
  urlAtiva: "/api/admin/ferramentas/graphify/grafo?token=t",
  atualizando: false,
  resultadoAtualizacao: null,
  onAtualizar: vi.fn(),
  onFecharResultado: vi.fn(),
};

describe("FerramentaViewer", () => {
  it("renderiza o iframe quando a ferramenta está online e tem URL", () => {
    render(<FerramentaViewer ativa={ferramenta()} {...BASE_PROPS} />);
    expect(screen.getByTitle("Visualização do Graphify")).toBeInTheDocument();
  });

  it("não renderiza iframe quando a ferramenta está offline", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta({ online: false })}
        {...BASE_PROPS}
        urlAtiva={null}
      />,
    );
    expect(screen.queryByTitle("Visualização do Graphify")).not.toBeInTheDocument();
    expect(screen.getByText("O artefato ainda não foi gerado.")).toBeInTheDocument();
  });

  it("mostra mensagem de servidor fora do ar para tipo 'servidor' offline", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta({ tipo: "servidor", online: false })}
        {...BASE_PROPS}
        urlAtiva={null}
      />,
    );
    expect(
      screen.getByText("O servidor desta ferramenta não está no ar."),
    ).toBeInTheDocument();
  });

  it("exibe botão 'Atualizar grafo' para graphify", () => {
    render(<FerramentaViewer ativa={ferramenta()} {...BASE_PROPS} />);
    expect(
      screen.getByRole("button", { name: /Atualizar grafo/ }),
    ).toBeInTheDocument();
  });

  it("exibe botão 'Atualizar índice' para gitnexus", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta({ id: "gitnexus", nome: "GitNexus" })}
        {...BASE_PROPS}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Atualizar índice/ }),
    ).toBeInTheDocument();
  });

  it("não exibe botão de atualizar para repowise", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta({ id: "repowise", nome: "Repowise" })}
        {...BASE_PROPS}
      />,
    );
    expect(screen.queryByRole("button", { name: /Atualizar/ })).not.toBeInTheDocument();
  });

  it("desabilita o botão enquanto atualizando e muda o label", () => {
    render(<FerramentaViewer ativa={ferramenta()} {...BASE_PROPS} atualizando={true} />);
    const btn = screen.getByRole("button", { name: /Atualizando/ });
    expect(btn).toBeDisabled();
  });

  it("chama onAtualizar com o id correto ao clicar no botão", () => {
    const onAtualizar = vi.fn();
    render(
      <FerramentaViewer ativa={ferramenta()} {...BASE_PROPS} onAtualizar={onAtualizar} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Atualizar grafo/ }));
    expect(onAtualizar).toHaveBeenCalledOnce();
    expect(onAtualizar).toHaveBeenCalledWith("graphify");
  });

  it("exibe painel de resultado de sucesso com role=status", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta()}
        {...BASE_PROPS}
        resultadoAtualizacao={{ id: "graphify", sucesso: true, saida: "ok" }}
      />,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Atualizado.");
  });

  it("exibe painel de resultado de falha", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta()}
        {...BASE_PROPS}
        resultadoAtualizacao={{ id: "graphify", sucesso: false, saida: "erro" }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Falha na atualização.");
  });

  it("não exibe painel de resultado de outra ferramenta", () => {
    render(
      <FerramentaViewer
        ativa={ferramenta({ id: "gitnexus", nome: "GitNexus" })}
        {...BASE_PROPS}
        resultadoAtualizacao={{ id: "graphify", sucesso: true, saida: "ok" }}
      />,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("chama onFecharResultado ao clicar no botão de fechar", () => {
    const onFecharResultado = vi.fn();
    render(
      <FerramentaViewer
        ativa={ferramenta()}
        {...BASE_PROPS}
        resultadoAtualizacao={{ id: "graphify", sucesso: true, saida: "ok" }}
        onFecharResultado={onFecharResultado}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Fechar mensagem" }));
    expect(onFecharResultado).toHaveBeenCalledOnce();
  });

  it("exibe link 'Abrir em nova aba' quando urlAtiva está preenchida", () => {
    render(<FerramentaViewer ativa={ferramenta()} {...BASE_PROPS} />);
    const link = screen.getByRole("link", { name: /Abrir em nova aba/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("não exibe link 'Abrir em nova aba' quando urlAtiva é null", () => {
    render(
      <FerramentaViewer ativa={ferramenta({ online: false })} {...BASE_PROPS} urlAtiva={null} />,
    );
    expect(screen.queryByRole("link", { name: /Abrir em nova aba/ })).not.toBeInTheDocument();
  });
});

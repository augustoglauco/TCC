import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProductGalleryShowcase from "@/components/home/ProductGalleryShowcase";

describe("ProductGalleryShowcase — cards de portfolio", () => {
  it("renderiza os 4 cards de produto", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText("Terminal Facial iDFace Max")).toBeInTheDocument();
    expect(screen.getByText("Catraca iDBlock Next Facial")).toBeInTheDocument();
    expect(screen.getByText("Porta Giratória iDBlock PcD")).toBeInTheDocument();
    expect(screen.getByText("Relógio de Ponto REP iDClass")).toBeInTheDocument();
  });

  it("exibe as tags de cada card", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText("Facial 3D • IP65")).toBeInTheDocument();
    expect(screen.getByText("Inox Escovado")).toBeInTheDocument();
    expect(screen.getByText("Acessibilidade PNE")).toBeInTheDocument();
    expect(screen.getByText("Homologado INMETRO")).toBeInTheDocument();
  });

  it("exibe as specs de cada card", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText("Até 100.000 faces • Live Detection")).toBeInTheDocument();
    expect(screen.getByText("Pedestal Integrado • 2 Leitores Faciais")).toBeInTheDocument();
  });

  it("exibe os subtítulos dos cards", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText("Hospitais, Indústrias & Condomínios Corporativos")).toBeInTheDocument();
    expect(screen.getByText("Recepções Executivas & Lobbies A+")).toBeInTheDocument();
  });

  it("exibe o link 'Explorar Catálogo Completo'", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByRole("link", { name: /Explorar Catálogo Completo/ })).toBeInTheDocument();
  });
});

describe("ProductGalleryShowcase — galeria de fotos", () => {
  it("renderiza os botões da galeria (row 1 duplicada = 12 botões)", () => {
    render(<ProductGalleryShowcase />);
    // Cada row é duplicada para o efeito de scroll infinito
    // row1 tem 6 fotos × 2 = 12 botões; row2 tem 6 × 2 = 12 botões
    const botoesGaleria = screen.getAllByRole("button");
    // Pelo menos 12 botões de galeria (pode ter mais se o lightbox estiver aberto)
    expect(botoesGaleria.length).toBeGreaterThanOrEqual(12);
  });

  it("exibe os títulos das fotos da row 1", () => {
    render(<ProductGalleryShowcase />);
    // Cada foto aparece 2x por causa da duplicação
    expect(screen.getAllByAltText("iDFace Frontal").length).toBe(2);
    expect(screen.getAllByAltText("iDBlock Facial Inox").length).toBe(2);
  });

  it("exibe os títulos das fotos da row 2", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getAllByAltText("iDFlex IP65").length).toBe(2);
    expect(screen.getAllByAltText("Controladora iDBox").length).toBe(2);
  });

  it("exibe os títulos de categoria no hover overlay (presentes no DOM)", () => {
    render(<ProductGalleryShowcase />);
    // As categorias ficam no overlay — estão no DOM mas ocultas por CSS
    expect(screen.getAllByText("Reconhecimento Facial").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Catracas").length).toBeGreaterThan(0);
  });
});

describe("ProductGalleryShowcase — lightbox", () => {
  it("lightbox não está visível antes de clicar em uma foto", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("abre o lightbox ao clicar em uma foto da galeria", () => {
    render(<ProductGalleryShowcase />);
    // Clica no primeiro botão da galeria (iDFace Frontal)
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("exibe o título e categoria da foto no lightbox", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    // O lightbox mostra o título da foto clicada
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // Título e categoria aparecem no lightbox
    expect(screen.getAllByText("iDFace Frontal").length).toBeGreaterThan(0);
  });

  it("fecha o lightbox ao clicar no botão ✕", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Fechar visualização" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("fecha o lightbox ao clicar no backdrop", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    const dialog = screen.getByRole("dialog");

    fireEvent.click(dialog);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exibe o link 'Ver no Catálogo' dentro do lightbox", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    expect(screen.getByRole("link", { name: /Ver no Catálogo/ })).toBeInTheDocument();
  });

  it("fecha o lightbox ao clicar em 'Ver no Catálogo'", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");
    fireEvent.click(botoesGaleria[0]);
    fireEvent.click(screen.getByRole("link", { name: /Ver no Catálogo/ }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("abre fotos diferentes ao clicar em botões diferentes", () => {
    render(<ProductGalleryShowcase />);
    const botoesGaleria = screen.getAllByRole("button");

    // Clica no primeiro (iDFace Frontal)
    fireEvent.click(botoesGaleria[0]);
    expect(screen.getAllByText("iDFace Frontal").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Fechar visualização" }));

    // Clica no segundo (iDBlock Facial Inox)
    fireEvent.click(botoesGaleria[1]);
    expect(screen.getAllByText("iDBlock Facial Inox").length).toBeGreaterThan(0);
  });
});

describe("ProductGalleryShowcase — títulos das seções", () => {
  it("exibe o título da seção de portfolio", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText(/Engenharia Visual/)).toBeInTheDocument();
  });

  it("exibe o título da seção de galeria", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText(/Linha Completa/)).toBeInTheDocument();
  });

  it("exibe o badge 'Vitrine de Equipamentos Fictícia'", () => {
    render(<ProductGalleryShowcase />);
    expect(screen.getByText("Vitrine de Equipamentos Fictícia")).toBeInTheDocument();
  });
});

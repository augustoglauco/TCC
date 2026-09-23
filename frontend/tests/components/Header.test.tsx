import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Header from "@/components/layout/Header";
import { useChatStore } from "@/lib/hooks/useChatStore";

describe("Header Component", () => {
  it("renderiza a marca/logo da empresa", () => {
    render(<Header />);
    expect(screen.getByText("Empresa Fictícia")).toBeInTheDocument();
  });

  it("abre a gaveta do menu mobile ao clicar no botão hambúrguer", () => {
    render(<Header />);
    const hamburgerBtn = screen.getByRole("button", { name: /abrir menu principal/i });
    expect(hamburgerBtn).toBeInTheDocument();

    // A gaveta inicia fechada
    expect(screen.queryByRole("navigation", { name: /navegação principal móvel/i })).not.toBeInTheDocument();

    // Clica para abrir
    fireEvent.click(hamburgerBtn);

    // Gaveta abre e exibe botão de chat e links de navegação
    expect(screen.getByRole("navigation", { name: /navegação principal móvel/i })).toBeInTheDocument();
    expect(screen.getByText("Abrir Chat / Assistente IA")).toBeInTheDocument();
  });

  it("abre o chat ao clicar no botão 'Chat' do cabeçalho", () => {
    useChatStore.setState({ isOpen: false });
    render(<Header />);

    const chatHeaderBtn = screen.getByRole("button", { name: /💬/i });
    fireEvent.click(chatHeaderBtn);

    expect(useChatStore.getState().isOpen).toBe(true);
  });
});

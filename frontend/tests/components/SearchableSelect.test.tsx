import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SearchableSelect from "@/components/ui/SearchableSelect";

const MOCK_OPTIONS = [
  { value: "1", label: "#1 - Gravador NVD", sublabel: "CFTV" },
  { value: "2", label: "#2 - Câmera IP", sublabel: "CFTV" },
  { value: "3", label: "#3 - Switch PoE 8 Portas", sublabel: "Redes" },
];

describe("SearchableSelect Component", () => {
  it("exibe o placeholder quando nenhum valor está selecionado", () => {
    render(
      <SearchableSelect
        options={MOCK_OPTIONS}
        value=""
        onChange={vi.fn()}
        placeholder="-- Pesquise um produto --"
      />
    );

    expect(screen.getByText("-- Pesquise um produto --")).toBeInTheDocument();
  });

  it("abre o menu de busca ao clicar no botão", async () => {
    const user = userEvent.setup();
    render(
      <SearchableSelect
        options={MOCK_OPTIONS}
        value=""
        onChange={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button"));

    expect(screen.getByPlaceholderText("Digite para filtrar produtos...")).toBeInTheDocument();
    expect(screen.getByText("#1 - Gravador NVD")).toBeInTheDocument();
    expect(screen.getByText("#2 - Câmera IP")).toBeInTheDocument();
  });

  it("filtra as opções conforme o usuário digita", async () => {
    const user = userEvent.setup();
    render(
      <SearchableSelect
        options={MOCK_OPTIONS}
        value=""
        onChange={vi.fn()}
      />
    );

    await user.click(screen.getByRole("button"));
    const input = screen.getByPlaceholderText("Digite para filtrar produtos...");
    await user.type(input, "Switch");

    expect(screen.getByText("#3 - Switch PoE 8 Portas")).toBeInTheDocument();
    expect(screen.queryByText("#1 - Gravador NVD")).not.toBeInTheDocument();
    expect(screen.queryByText("#2 - Câmera IP")).not.toBeInTheDocument();
  });

  it("chama onChange com a chave selecionada ao clicar numa opção", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchableSelect
        options={MOCK_OPTIONS}
        value=""
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByText("#2 - Câmera IP"));

    expect(onChange).toHaveBeenCalledWith("2");
  });

  it("permite limpar a seleção ao clicar no botão de fechar", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SearchableSelect
        options={MOCK_OPTIONS}
        value="2"
        onChange={onChange}
      />
    );

    const clearButton = screen.getByTitle("Limpar seleção");
    await user.click(clearButton);

    expect(onChange).toHaveBeenCalledWith("");
  });
});

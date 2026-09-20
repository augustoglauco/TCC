import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ImageUploader from "@/components/chat/ImageUploader";

/** Cria um File PNG mínimo para simular seleção no input. */
function makePngFile(name = "produto.png"): File {
  // 8 bytes de PNG válido (magic bytes suficientes para o componente aceitar)
  const bytes = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  return new File([bytes], name, { type: "image/png" });
}

describe("ImageUploader", () => {
  it("renderiza o botão de upload habilitado por padrão", () => {
    render(<ImageUploader onImageSelected={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Enviar imagem" })).not.toBeDisabled();
  });

  it("desabilita o botão quando disabled=true", () => {
    render(<ImageUploader disabled onImageSelected={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Enviar imagem" })).toBeDisabled();
  });

  it("chama onImageSelected com base64 e nome do arquivo ao selecionar PNG", async () => {
    const onImageSelected = vi.fn();
    const user = userEvent.setup();

    render(<ImageUploader onImageSelected={onImageSelected} />);

    const input = document.querySelector("input[type='file']") as HTMLInputElement;
    await user.upload(input, makePngFile("produto.png"));

    await waitFor(() => {
      expect(onImageSelected).toHaveBeenCalledTimes(1);
    });

    const [base64, name] = onImageSelected.mock.calls[0] as [string, string];
    expect(name).toBe("produto.png");
    // base64 não deve conter o prefixo "data:..."
    expect(base64).not.toContain("data:");
    expect(base64.length).toBeGreaterThan(0);
  });

  it("chama onImageSelected ao selecionar JPG", async () => {
    const onImageSelected = vi.fn();
    const user = userEvent.setup();

    render(<ImageUploader onImageSelected={onImageSelected} />);

    const jpgBytes = new Uint8Array([0xff, 0xd8, 0xff, 0xe0]);
    const jpgFile = new File([jpgBytes], "foto.jpg", { type: "image/jpeg" });
    const input = document.querySelector("input[type='file']") as HTMLInputElement;
    await user.upload(input, jpgFile);

    await waitFor(() => {
      expect(onImageSelected).toHaveBeenCalledWith(expect.any(String), "foto.jpg");
    });
  });

  it("não chama onImageSelected quando nenhum arquivo é selecionado", async () => {
    const onImageSelected = vi.fn();
    render(<ImageUploader onImageSelected={onImageSelected} />);

    // Dispara change sem arquivo (value vazio — simula cancelar o diálogo)
    const input = document.querySelector("input[type='file']") as HTMLInputElement;
    input.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(onImageSelected).not.toHaveBeenCalled();
    });
  });
});

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FileTypeIcon } from "@/components/ui/FileTypeIcon";

describe("FileTypeIcon", () => {
  it.each([
    ["Manual_GD30.pdf", "Arquivo PDF"],
    ["idaccess.md", "Arquivo Markdown"],
    ["notas.txt", "Arquivo de texto"],
    ["precos.csv", "Arquivo CSV"],
    ["instalador.exe", "Arquivo"],
    ["semextensao", "Arquivo"],
  ])("escolhe o ícone certo para %s", (filename, rotulo) => {
    render(<FileTypeIcon filename={filename} />);

    expect(screen.getByRole("img", { name: rotulo })).toBeInTheDocument();
  });

  it("ignora maiúsculas na extensão", () => {
    render(<FileTypeIcon filename="MANUAL.PDF" />);

    expect(screen.getByRole("img", { name: "Arquivo PDF" })).toBeInTheDocument();
  });
});

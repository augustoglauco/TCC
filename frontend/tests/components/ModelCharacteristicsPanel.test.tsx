import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";

const CARACTERISTICAS = {
  source: "openrouter" as const,
  tag: "openai/gpt-4o-mini",
  is_multimodal: true,
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  parameter_size: null,
  quantization: null,
  pricing_prompt_per_1k: 0.00015,
  pricing_completion_per_1k: 0.0006,
  knowledge_cutoff: "2023-10-31",
  fetched_at: new Date().toISOString(),
};

describe("ModelCharacteristicsPanel", () => {
  it("mostra as modalidades de entrada e saída explicitamente (não um badge binário)", () => {
    render(
      <ModelCharacteristicsPanel
        data={CARACTERISTICAS}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
      />,
    );

    // "Texto" aparece tanto na seção de Entrada quanto na de Saída (ambas
    // incluem texto na fixture) — por isso getAllByText, não getByText.
    expect(screen.getAllByText("Texto").length).toBeGreaterThan(0);
    expect(screen.getByText("Imagem")).toBeInTheDocument();
    expect(screen.queryByText(/multimodal/i)).not.toBeInTheDocument();
  });

  it("mostra contexto formatado em K tokens", () => {
    render(
      <ModelCharacteristicsPanel
        data={CARACTERISTICAS}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText(/128K tokens/)).toBeInTheDocument();
  });

  it("mostra texto de carregamento quando loading e sem dado ainda", () => {
    render(
      <ModelCharacteristicsPanel data={null} loading={true} error={null} onRefresh={vi.fn()} />,
    );

    expect(screen.getByText(/Carregando características/i)).toBeInTheDocument();
  });

  it("mostra mensagem discreta quando não há dado nem erro (404)", () => {
    render(
      <ModelCharacteristicsPanel data={null} loading={false} error={null} onRefresh={vi.fn()} />,
    );

    expect(screen.getByText(/indisponíveis no momento/i)).toBeInTheDocument();
  });

  it("chama onRefresh ao clicar no botão de atualizar", () => {
    const onRefresh = vi.fn();
    render(
      <ModelCharacteristicsPanel
        data={CARACTERISTICAS}
        loading={false}
        error={null}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(screen.getByLabelText("Atualizar características"));

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

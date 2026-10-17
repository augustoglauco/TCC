import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MetricCounters from "@/components/home/MetricCounters";

describe("MetricCounters", () => {
  it("renderiza as 4 métricas industriais de confiabilidade e performance", () => {
    render(<MetricCounters />);
    expect(screen.getByText("99.9%")).toBeInTheDocument();
    expect(screen.getByText(/Precisão em Reconhecimento Facial/i)).toBeInTheDocument();
    expect(screen.getByText("< 0.2s")).toBeInTheDocument();
    expect(screen.getByText(/Velocidade de Leitura e Autenticação/i)).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText(/Conformidade Portaria 671 MTE/i)).toBeInTheDocument();
    expect(screen.getByText("24/7")).toBeInTheDocument();
    expect(screen.getByText(/Assistente de IA/i)).toBeInTheDocument();
  });
});

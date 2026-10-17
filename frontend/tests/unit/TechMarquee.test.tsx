import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TechMarquee from "@/components/home/TechMarquee";

describe("TechMarquee", () => {
  it("renderiza os selos de tecnologia da Control iD", () => {
    render(<TechMarquee />);
    expect(screen.getAllByText(/Reconhecimento Facial/i)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Catracas em Inox/i)[0]).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";

function ExemploTabs() {
  return (
    <Tabs defaultValue="a">
      <TabsList>
        <TabsTrigger value="a">Aba A</TabsTrigger>
        <TabsTrigger value="b">Aba B</TabsTrigger>
        <TabsTrigger value="c" disabled>
          Aba C
        </TabsTrigger>
      </TabsList>
      <TabsContent value="a">Conteúdo A</TabsContent>
      <TabsContent value="b">Conteúdo B</TabsContent>
      <TabsContent value="c">Conteúdo C</TabsContent>
    </Tabs>
  );
}

describe("Tabs", () => {
  it("mostra o conteúdo da aba padrão e troca ao clicar em outra aba", async () => {
    const user = userEvent.setup();
    render(<ExemploTabs />);

    expect(screen.getByText("Conteúdo A")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo B")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Aba B" }));

    expect(screen.getByText("Conteúdo B")).toBeInTheDocument();
    expect(screen.queryByText("Conteúdo A")).not.toBeInTheDocument();
  });

  it("não deixa selecionar uma aba desabilitada", async () => {
    const user = userEvent.setup();
    render(<ExemploTabs />);

    await user.click(screen.getByRole("tab", { name: "Aba C" }));

    expect(screen.queryByText("Conteúdo C")).not.toBeInTheDocument();
  });
});

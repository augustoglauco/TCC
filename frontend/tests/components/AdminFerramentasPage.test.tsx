import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminFerramentasPage from "@/app/admin/ferramentas/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as ferramentasApi from "@/lib/api/ferramentas";

function ferramenta(
  over: Partial<ferramentasApi.FerramentaStatus> = {},
): ferramentasApi.FerramentaStatus {
  return {
    id: "graphify",
    nome: "Graphify",
    descricao: "Grafo estrutural por AST.",
    tipo: "artefato",
    url: "/api/admin/ferramentas/graphify/grafo",
    online: true,
    detalhe: "/repo/graphify-out/graph.html (3.0 MB)",
    comando: "graphify update .",
    ...over,
  };
}

const RESPOSTA: ferramentasApi.FerramentasResposta = {
  ferramentas: [
    ferramenta(),
    ferramenta({
      id: "repowise",
      nome: "Repowise",
      descricao: "Wiki viva do código.",
      tipo: "servidor",
      url: "http://localhost:3002/repos/abc123/overview",
      online: false,
      detalhe: "Sem resposta em http://localhost:3002/repos/abc123/overview (ConnectError)",
      comando: "repowise serve",
    }),
    ferramenta({
      id: "gitnexus",
      nome: "GitNexus",
      descricao: "Grafo de chamadas e fluxos.",
      tipo: "servidor",
      url: "http://localhost:4747",
      online: true,
      detalhe: "HTTP 200",
      comando: "node .gitnexus/run.cjs serve",
    }),
  ],
};

function logarComoAdmin() {
  useAuthStore.setState({
    user: { id: 1, nome: "Admin Teste", email: "admin@example.com", perfil: "Admin" },
    token: "mock-token",
  });
}

describe("AdminFerramentasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("nega acesso a quem não é administrador", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "João Cliente", email: "joao@example.com", perfil: "Cliente" },
      token: "mock-token",
    });

    render(<AdminFerramentasPage />);
    expect(screen.getByText("Acesso restrito")).toBeInTheDocument();
  });

  it("lista as três ferramentas com o estado de cada uma", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockResolvedValue(RESPOSTA);

    render(<AdminFerramentasPage />);

    // "Graphify" aparece duas vezes quando está selecionado: no cartão e no
    // cabeçalho do quadro de visualização — daí o getAllByText.
    await waitFor(() => expect(screen.getAllByText("Graphify").length).toBeGreaterThan(0));
    expect(screen.getByText("Repowise")).toBeInTheDocument();
    expect(screen.getByText("GitNexus")).toBeInTheDocument();
    expect(screen.getByText("Gerado")).toBeInTheDocument();
    expect(screen.getByText("Fora do ar")).toBeInTheDocument();
    expect(screen.getByText("No ar")).toBeInTheDocument();
  });

  it("mostra o comando de como subir a ferramenta que está fora do ar", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockResolvedValue(RESPOSTA);

    render(<AdminFerramentasPage />);

    await waitFor(() => expect(screen.getByText("Repowise")).toBeInTheDocument());
    expect(screen.getAllByText("repowise serve").length).toBeGreaterThan(0);
  });

  it("embute a primeira ferramenta disponível e autentica o artefato pela URL", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockResolvedValue(RESPOSTA);

    render(<AdminFerramentasPage />);

    const iframe = await screen.findByTitle("Visualização do Graphify");
    // O iframe não manda cabeçalho Authorization — o token precisa ir na
    // query string, senão o backend responde 403 e o quadro fica vazio.
    expect(iframe.getAttribute("src")).toContain("/api/admin/ferramentas/graphify/grafo");
    expect(iframe.getAttribute("src")).toContain("token=mock-token");
  });

  it("troca a visualização ao selecionar outra ferramenta", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockResolvedValue(RESPOSTA);

    render(<AdminFerramentasPage />);
    await screen.findByTitle("Visualização do Graphify");

    fireEvent.click(screen.getByText("GitNexus"));

    const iframe = await screen.findByTitle("Visualização do GitNexus");
    // A SPA do GitNexus chama o backend dela numa URL fixa de build; o
    // `?server=` aponta essa chamada para a origem de onde a página veio —
    // sem ele a tela fica em "Start your local server" (ver
    // `urlDeVisualizacao` em `lib/api/ferramentas.ts`).
    const src = new URL(iframe.getAttribute("src") as string);
    expect(src.origin).toBe("http://localhost:4747");
    expect(src.searchParams.get("server")).toBe("http://localhost:4747");
  });

  it("não embute iframe de ferramenta fora do ar — mostra o comando no lugar", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockResolvedValue(RESPOSTA);

    render(<AdminFerramentasPage />);
    await screen.findByTitle("Visualização do Graphify");

    fireEvent.click(screen.getByText("Repowise"));

    await waitFor(() =>
      expect(screen.getByText("O servidor desta ferramenta não está no ar.")).toBeInTheDocument(),
    );
    expect(screen.queryByTitle("Visualização do Repowise")).not.toBeInTheDocument();
  });

  it("exibe erro quando a consulta ao backend falha", async () => {
    logarComoAdmin();
    vi.spyOn(ferramentasApi, "fetchFerramentas").mockRejectedValue(
      new Error("Falha ao consultar as ferramentas (500)"),
    );

    render(<AdminFerramentasPage />);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Falha ao consultar as ferramentas (500)",
      ),
    );
  });
});

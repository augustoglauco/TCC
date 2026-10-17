import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminDatasetsPage from "@/app/admin/datasets/page";
import * as datasetsApi from "@/lib/api/datasets";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

function conjunto(over: Partial<datasetsApi.ConjuntoStatus> = {}): datasetsApi.ConjuntoStatus {
  return {
    id: "rag_docs",
    nome: "RAG documentos",
    meta: 180,
    total: 18,
    pendentes: 18,
    aprovados: 0,
    corrigidos: 0,
    descartados: 0,
    revisao_automatica: false,
    existe: true,
    ...over,
  };
}

const CONJUNTOS: datasetsApi.DatasetsResposta = {
  conjuntos: [
    conjunto(),
    conjunto({
      id: "rag_banco",
      nome: "RAG banco",
      meta: 80,
      total: 0,
      pendentes: 0,
      revisao_automatica: true,
      existe: false,
    }),
  ],
};

const ITENS: datasetsApi.ItensResposta = {
  conjunto: "rag_docs",
  total: 2,
  itens: [
    {
      indice: 0,
      id: "q1",
      status: "pendente",
      campos: { pergunta: "Qual a tensão do iDFace?", trecho: "Alimentação: 12 Vdc" },
    },
    { indice: 1, id: "q2", status: "pendente", campos: { pergunta: "Tem Wi-Fi?" } },
  ],
};

function logarComoAdmin() {
  useAuthStore.setState({
    user: { id: 1, nome: "Admin Teste", email: "admin@example.com", perfil: "Admin" },
    token: "mock-token",
  });
}

describe("AdminDatasetsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ user: null, token: null });
    vi.spyOn(datasetsApi, "fetchTarefas").mockResolvedValue([]);
  });

  it("nega acesso a quem não é administrador", () => {
    useAuthStore.setState({
      user: { id: 2, nome: "João", email: "joao@example.com", perfil: "Cliente" },
      token: "mock-token",
    });

    render(<AdminDatasetsPage />);
    expect(screen.getByText(/restrita a administradores/i)).toBeInTheDocument();
  });

  it("mostra o progresso de cada conjunto como total sobre a meta", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue(CONJUNTOS);
    vi.spyOn(datasetsApi, "fetchItens").mockResolvedValue(ITENS);

    render(<AdminDatasetsPage />);

    await waitFor(() => expect(screen.getByText("RAG documentos")).toBeInTheDocument());
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("/ 180")).toBeInTheDocument();
    expect(screen.getByText("RAG banco")).toBeInTheDocument();
  });

  it("abre a fila no primeiro conjunto com pendentes e mostra os campos do item", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue(CONJUNTOS);
    vi.spyOn(datasetsApi, "fetchItens").mockResolvedValue(ITENS);

    render(<AdminDatasetsPage />);

    await waitFor(() =>
      expect(screen.getByDisplayValue("Qual a tensão do iDFace?")).toBeInTheDocument(),
    );
    // O trecho de origem vem junto do item: é o que troca ~1,5 min de caça
    // no PDF por ~10 s de leitura lado a lado.
    expect(screen.getByDisplayValue("Alimentação: 12 Vdc")).toBeInTheDocument();
  });

  it("aprovar grava sem campos e avança para o item seguinte", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue(CONJUNTOS);
    vi.spyOn(datasetsApi, "fetchItens").mockResolvedValue(ITENS);
    const revisar = vi.spyOn(datasetsApi, "revisarItem").mockResolvedValue({
      indice: 0,
      id: "q1",
      status: "aprovado",
      campos: {},
    });

    render(<AdminDatasetsPage />);
    await waitFor(() =>
      expect(screen.getByDisplayValue("Qual a tensão do iDFace?")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: /Aprovar/ }));

    await waitFor(() =>
      expect(revisar).toHaveBeenCalledWith("rag_docs", 0, "aprovado", "mock-token", undefined),
    );
    await waitFor(() => expect(screen.getByDisplayValue("Tem Wi-Fi?")).toBeInTheDocument());
  });

  it("editar um campo transforma a decisão em correção e manda só o que mudou", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue(CONJUNTOS);
    vi.spyOn(datasetsApi, "fetchItens").mockResolvedValue(ITENS);
    const revisar = vi.spyOn(datasetsApi, "revisarItem").mockResolvedValue({
      indice: 0,
      id: "q1",
      status: "corrigido",
      campos: {},
    });

    render(<AdminDatasetsPage />);
    await waitFor(() =>
      expect(screen.getByDisplayValue("Qual a tensão do iDFace?")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByDisplayValue("Qual a tensão do iDFace?"), {
      target: { value: "Qual a tensão de alimentação do iDFace?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Salvar correção/ }));

    await waitFor(() =>
      expect(revisar).toHaveBeenCalledWith("rag_docs", 0, "corrigido", "mock-token", {
        pergunta: "Qual a tensão de alimentação do iDFace?",
      }),
    );
  });

  it("conjunto de gabarito automático aparece sem fila de revisão", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue({
      conjuntos: [CONJUNTOS.conjuntos[1]],
    });
    const itens = vi.spyOn(datasetsApi, "fetchItens");

    render(<AdminDatasetsPage />);

    await waitFor(() => expect(screen.getByText(/sem fila/i)).toBeInTheDocument());
    expect(screen.getByText("automático")).toBeInTheDocument();
    expect(itens).not.toHaveBeenCalled();
  });

  it("dispara a triagem e mostra o log da tarefa", async () => {
    logarComoAdmin();
    vi.spyOn(datasetsApi, "fetchConjuntos").mockResolvedValue(CONJUNTOS);
    vi.spyOn(datasetsApi, "fetchItens").mockResolvedValue(ITENS);
    const tarefa = {
      id: "t1",
      tipo: "triagem",
      rotulo: "Triagem: roteador + imagem nos 10 candidatos",
      estado: "concluida",
      iniciada_em: 1760000000,
      terminada_em: 1760000100,
      codigo: 0,
      total_linhas: 1,
    };
    vi.spyOn(datasetsApi, "iniciarTarefa").mockResolvedValue(tarefa);
    vi.spyOn(datasetsApi, "fetchTarefas").mockResolvedValue([tarefa]);
    vi.spyOn(datasetsApi, "fetchTarefa").mockResolvedValue({
      ...tarefa,
      linhas: ["candidato 1/10: gemma4:12b"],
      proximo_offset: 1,
    });

    render(<AdminDatasetsPage />);
    await waitFor(() => expect(screen.getByText("Tarefas longas")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Triagem: roteador + imagem"));
    fireEvent.click(screen.getAllByRole("button", { name: "Iniciar" })[1]);

    await waitFor(() => expect(screen.getByText("candidato 1/10: gemma4:12b")).toBeInTheDocument());
  });
});

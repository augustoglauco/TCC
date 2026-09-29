import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cancelarAgendamento,
  criarAgendamentoManual,
  fetchAdminAgendamentos,
  fetchGoogleCalendarEvents,
  fetchMeusAgendamentos,
} from "@/lib/api/agendamentos";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("agendamentos API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("fetchMeusAgendamentos", () => {
    it("chama endpoint correto e retorna lista de agendamentos", async () => {
      const mockData = [
        {
          id: "ag-1",
          user_email: "cliente@teste.com",
          nome_cliente: "Cliente Teste",
          data_hora_inicio: "2026-10-10T10:00:00Z",
          data_hora_fim: "2026-10-10T10:30:00Z",
          status: "confirmado",
          origem: "chat",
          criado_em: "2026-09-29T10:00:00Z",
          atualizado_em: "2026-09-29T10:00:00Z",
        },
      ];
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(mockData, 200));
      vi.stubGlobal("fetch", fetchMock);

      const res = await fetchMeusAgendamentos("cliente@teste.com");
      expect(res).toEqual(mockData);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/agendamentos/meus?user_email=cliente%40teste.com")
      );
    });

    it("lança erro amigável se a requisição falhar", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Erro interno no servidor" }, 500)));
      await expect(fetchMeusAgendamentos("cliente@teste.com")).rejects.toThrow("Erro interno no servidor");
    });
  });

  describe("cancelarAgendamento", () => {
    it("chama endpoint POST com id e email do usuário", async () => {
      const mockUpdated = {
        id: "ag-1",
        status: "cancelado",
      };
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(mockUpdated, 200));
      vi.stubGlobal("fetch", fetchMock);

      const res = await cancelarAgendamento("ag-1", "cliente@teste.com");
      expect(res).toEqual(mockUpdated);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/agendamentos/ag-1/cancelar?user_email=cliente%40teste.com"),
        expect.objectContaining({ method: "POST" })
      );
    });

    it("lança erro com o detail do backend se o status for 400 ou 403", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(jsonResponse({ detail: "Este agendamento já está cancelado." }, 400))
      );
      await expect(cancelarAgendamento("ag-1", "cliente@teste.com")).rejects.toThrow(
        "Este agendamento já está cancelado."
      );
    });
  });

  describe("fetchAdminAgendamentos", () => {
    it("passa parâmetros de filtro na query string", async () => {
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse([], 200));
      vi.stubGlobal("fetch", fetchMock);

      await fetchAdminAgendamentos({
        filtroEmail: "teste",
        status: "confirmado",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/agendamentos\/admin\?.*filtro_email=teste.*status=confirmado/)
      );
    });
  });

  describe("criarAgendamentoManual", () => {
    it("envia payload via POST para endpoint administrativo", async () => {
      const mockCreated = { id: "ag-manual-1", status: "confirmado" };
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(mockCreated, 201));
      vi.stubGlobal("fetch", fetchMock);

      const payload = {
        user_email: "manual@teste.com",
        nome_cliente: "Admin Cliente",
        data_hora_inicio: "2026-10-15T14:00:00Z",
      };

      const res = await criarAgendamentoManual(payload);
      expect(res).toEqual(mockCreated);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/agendamentos/admin/manual"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      );
    });

    it("lança erro caso retorne 409 conflito de horário", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(jsonResponse({ detail: "Horário indisponível na agenda Google." }, 409))
      );

      await expect(
        criarAgendamentoManual({
          user_email: "manual@teste.com",
          nome_cliente: "Admin Cliente",
          data_hora_inicio: "2026-10-15T14:00:00Z",
        })
      ).rejects.toThrow("Horário indisponível na agenda Google.");
    });
  });

  describe("fetchGoogleCalendarEvents", () => {
    it("consulta eventos do Google Calendar via admin", async () => {
      const mockEvents = [{ id: "evt-1", summary: "Visita Google" }];
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(mockEvents, 200));
      vi.stubGlobal("fetch", fetchMock);

      const res = await fetchGoogleCalendarEvents({
        timeMin: "2026-10-01T00:00:00Z",
        timeMax: "2026-10-31T23:59:59Z",
      });

      expect(res).toEqual(mockEvents);
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/agendamentos\/admin\/google-events\?.*time_min=.*time_max=/)
      );
    });
  });
});

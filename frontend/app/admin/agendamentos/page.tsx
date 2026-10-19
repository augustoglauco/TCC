"use client";

import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useAdminAgendamentos, useAgendamentoManual } from "@/lib/hooks/useAdminAgendamentos";
import { AcessoRestritoAgendamentos } from "./AcessoRestritoAgendamentos";
import { AgendamentosSystemTab } from "./AgendamentosSystemTab";
import { GoogleCalendarTab } from "./GoogleCalendarTab";
import { AgendamentoManualModal } from "./AgendamentoManualModal";
import { AgendamentosHeader } from "./AgendamentosHeader";
import { AgendamentosMetrics } from "./AgendamentosMetrics";
import { AgendamentosTabs } from "./AgendamentosTabs";

export default function AdminAgendamentosPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  const dados = useAdminAgendamentos(isAdmin);
  const manual = useAgendamentoManual(dados.recarregarSistema);

  if (!user || !isAdmin) return <AcessoRestritoAgendamentos />;

  const { agendamentos } = dados;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-8">
      <AgendamentosHeader onAgendar={manual.abrir} />

      <AgendamentosMetrics
        total={agendamentos.length}
        confirmados={agendamentos.filter((a) => a.status === "confirmado").length}
        cancelados={agendamentos.filter((a) => a.status === "cancelado").length}
      />

      <AgendamentosTabs activeTab={dados.activeTab} onChange={dados.setActiveTab} />

      {dados.activeTab === "sistema" && (
        <AgendamentosSystemTab
          agendamentos={agendamentos}
          loading={dados.loading}
          error={dados.error}
          filtroEmail={dados.filtroEmail}
          filtroStatus={dados.filtroStatus}
          onFiltroEmailChange={dados.setFiltroEmail}
          onFiltroStatusChange={dados.setFiltroStatus}
          onFiltrar={dados.recarregarSistema}
          onCancelar={dados.cancelar}
        />
      )}

      {dados.activeTab === "google" && (
        <GoogleCalendarTab
          googleEvents={dados.googleEvents}
          loading={dados.loading}
          error={dados.error}
          onAtualizar={dados.recarregarGoogle}
        />
      )}

      {manual.aberto && (
        <AgendamentoManualModal
          form={manual.form}
          submitting={manual.submitting}
          error={manual.error}
          onFormChange={manual.setForm}
          onSubmit={manual.submit}
          onClose={manual.fechar}
        />
      )}
    </div>
  );
}

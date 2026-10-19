/** Título do modal do chat: indicador "online" + nome + selo da stack (R3). */
export function ChatModalTitulo() {
  return (
    <div className="flex items-center gap-2 text-slate-900">
      <span className="relative flex h-2.5 w-2.5 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
      </span>
      <span className="font-extrabold text-sm sm:text-base tracking-tight">
        Chat com Agente Virtual
      </span>
      <span className="hidden sm:inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] sm:text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
        Ollama + Dual MCP
      </span>
    </div>
  );
}

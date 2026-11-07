import Link from "next/link";
import { User } from "@/lib/types/auth";
import type { ChaveParceiroAtiva } from "@/lib/api/parceirosB2b";

const BOTAO_LINK = "font-semibold underline disabled:opacity-50";

const PERFIL_CLASSES: Record<string, string> = {
  admin: "bg-purple-50 text-purple-700 border-purple-200",
  cliente: "bg-emerald-50 text-emerald-700 border-emerald-200",
  esporadico: "bg-blue-50 text-blue-700 border-blue-200",
};
const PERFIL_PADRAO = "bg-amber-50 text-amber-700 border-amber-200";

export function ehAdmin(perfil: string): boolean {
  return perfil.toLowerCase() === "admin";
}

export function AcessoRestrito() {
  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-3xl font-bold shadow-xs border border-rose-200">
        🔒
      </div>
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Acesso Restrito ao Administrador</h1>
        <p className="mt-2 text-sm text-slate-600">
          Apenas usuários com perfil <strong>Administrador (Admin)</strong> têm permissão para
          acessar a gestão de contas e usuários.
        </p>
      </div>

      <div className="flex flex-col gap-3 pt-2">
        <Link
          href="/conta/login"
          className="rounded-xl bg-purple-600 px-4 py-3 text-sm font-bold text-white shadow-xs hover:bg-purple-700 transition-colors"
        >
          Entrar como Administrador &rarr;
        </Link>
        <Link
          href="/"
          className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
        >
          Voltar ao Início
        </Link>
      </div>
    </div>
  );
}

export function UsuariosCabecalho() {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Gerenciamento de Usuários
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 mt-1">
          Consulte usuários cadastrados, atribua perfis comerciais e crie novos administradores ou
          clientes.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Link
          href="/conta/cadastro"
          className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-purple-700 transition-colors cursor-pointer"
        >
          <span>+</span>
          <span>Novo Usuário / Admin</span>
        </Link>
      </div>
    </div>
  );
}

function CartaoMetrica(props: {
  rotulo: string;
  valor: number;
  caixa: string;
  rotuloCor: string;
  valorCor: string;
}) {
  return (
    <div className={`rounded-xl border p-4 shadow-2xs ${props.caixa}`}>
      <span className={`text-xs font-semibold uppercase tracking-wider block ${props.rotuloCor}`}>
        {props.rotulo}
      </span>
      <span className={`mt-1 text-2xl font-bold block ${props.valorCor}`}>{props.valor}</span>
    </div>
  );
}

export function MetricasUsuarios({ users }: { users: User[] }) {
  const totalAdmins = users.filter((u) => ehAdmin(u.perfil)).length;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <CartaoMetrica
        rotulo="Total de Usuários"
        valor={users.length}
        caixa="border-slate-200 bg-white"
        rotuloCor="text-slate-500"
        valorCor="text-slate-900"
      />
      <CartaoMetrica
        rotulo="Administradores (Admin)"
        valor={totalAdmins}
        caixa="border-purple-100 bg-purple-50/50"
        rotuloCor="text-purple-700"
        valorCor="text-purple-900"
      />
      <CartaoMetrica
        rotulo="Clientes / Leads"
        valor={users.length - totalAdmins}
        caixa="border-blue-100 bg-blue-50/50"
        rotuloCor="text-blue-700"
        valorCor="text-blue-900"
      />
    </div>
  );
}

export function FiltrosUsuarios(props: {
  termo: string;
  onTermo: (v: string) => void;
  perfil: string;
  onPerfil: (v: string) => void;
}) {
  return (
    <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
      <div className="relative flex-1">
        <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">🔍</span>
        <input
          type="text"
          value={props.termo}
          onChange={(e) => props.onTermo(e.target.value)}
          placeholder="Buscar por nome ou e-mail..."
          className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-4 text-xs text-slate-900 placeholder:text-slate-400 focus:border-purple-600 focus:outline-hidden"
        />
      </div>

      <select
        value={props.perfil}
        onChange={(e) => props.onPerfil(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:border-purple-600 focus:outline-hidden"
      >
        <option value="todos">Todos os Perfis</option>
        <option value="admin">Administrador (Admin)</option>
        <option value="cliente">Cliente (Recorrente)</option>
        <option value="esporadico">Esporádico</option>
        <option value="lead">Lead</option>
      </select>
    </div>
  );
}

function PerfilBadge({ perfil }: { perfil: string }) {
  const cor = PERFIL_CLASSES[perfil.toLowerCase()] ?? PERFIL_PADRAO;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold border ${cor}`}
    >
      {ehAdmin(perfil) ? "⚙️ Admin" : `👤 ${perfil}`}
    </span>
  );
}

export type AcoesChave = {
  emAndamento: number | null;
  onGerar: (clienteId: number, regenerar: boolean) => void;
  onRevogar: (clienteId: number) => void;
};

function ChaveB2bCelula(props: { user: User; chave?: ChaveParceiroAtiva; acoes: AcoesChave }) {
  const { user, chave, acoes } = props;
  const ocupado = acoes.emAndamento === user.id;
  if (ehAdmin(user.perfil) || user.id === 0) return <span className="text-slate-400">-</span>;
  if (!chave) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={ocupado}
          onClick={() => acoes.onGerar(user.id, false)}
          className={`${BOTAO_LINK} text-blue-600 hover:text-blue-800`}
        >
          Gerar chave B2B
        </button>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className="rounded bg-emerald-50 px-2 py-0.5 font-mono text-emerald-700 border border-emerald-200"
        title={`Criada em ${new Date(chave.criada_em).toLocaleString("pt-BR")}`}
      >
        {chave.prefixo}…
      </span>
      <button
        type="button"
        disabled={ocupado}
        onClick={() => acoes.onGerar(user.id, true)}
        className={`${BOTAO_LINK} text-blue-600 hover:text-blue-800`}
      >
        Gerar nova
      </button>
      <button
        type="button"
        disabled={ocupado}
        onClick={() => acoes.onRevogar(user.id)}
        className={`${BOTAO_LINK} text-rose-600 hover:text-rose-800`}
      >
        Revogar
      </button>
    </div>
  );
}

function UsuarioLinha(props: { user: User; chave?: ChaveParceiroAtiva; acoes: AcoesChave }) {
  const { user: u } = props;
  return (
    <tr className="hover:bg-slate-50/60 transition-colors">
      <td className="px-4 py-3.5 font-mono text-slate-400">#{u.id}</td>
      <td className="px-4 py-3.5 font-bold text-slate-900">
        <span title={u.email} className="cursor-help">
          {u.nome}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <PerfilBadge perfil={u.perfil} />
      </td>
      <td className="px-4 py-3.5 text-slate-500 text-[11px]">
        {u.perfil_motivo || "Cadastro direto no sistema"}
      </td>
      <td className="px-4 py-3.5 text-[11px]">
        <ChaveB2bCelula user={u} chave={props.chave} acoes={props.acoes} />
      </td>
      <td className="px-4 py-3.5 text-right">
        <Link
          href={`/pedidos/historico?email=${encodeURIComponent(u.email)}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 underline"
        >
          <span>Ver Pedidos</span>
        </Link>
      </td>
    </tr>
  );
}

export function UsuariosVazio() {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center space-y-2">
      <div className="text-3xl">👥</div>
      <h3 className="text-sm font-bold text-slate-800">Nenhum usuário encontrado</h3>
      <p className="text-xs text-slate-500">
        Tente ajustar os termos de busca ou filtro de perfil.
      </p>
    </div>
  );
}

export function UsuariosTabela(props: {
  users: User[];
  chaves: Record<number, ChaveParceiroAtiva>;
  acoes: AcoesChave;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-2xs">
      <table className="w-full text-left text-xs text-slate-700">
        <thead className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500">
          <tr>
            <th className="px-4 py-3">ID</th>
            <th className="px-4 py-3">Nome do Usuário</th>
            <th className="px-4 py-3">Perfil Comercial</th>
            <th className="px-4 py-3">Origem / Motivo</th>
            <th className="px-4 py-3">Chave B2B (MCP)</th>
            <th className="px-4 py-3 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {props.users.map((u) => (
            <UsuarioLinha key={u.id} user={u} chave={props.chaves[u.id]} acoes={props.acoes} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

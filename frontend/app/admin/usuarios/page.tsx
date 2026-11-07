"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { fetchUsers } from "@/lib/api/auth";
import { User } from "@/lib/types/auth";
import {
  fetchChavesParceiros,
  gerarChaveParceiro,
  revogarChaveParceiro,
  type ChaveParceiroAtiva,
  type ChaveParceiroGerada,
} from "@/lib/api/parceirosB2b";
import { ChaveB2bDialog } from "@/components/admin/ChaveB2bDialog";

import {
  AcessoRestrito,
  FiltrosUsuarios,
  MetricasUsuarios,
  UsuariosCabecalho,
  UsuariosTabela,
  UsuariosVazio,
  type AcoesChave,
} from "@/components/admin/UsuariosPainel";

function filtrarUsuarios(users: User[], termo: string, perfilFiltro: string): User[] {
  const t = termo.toLowerCase();
  return users.filter((u) => {
    const matchTermo = u.nome.toLowerCase().includes(t) || u.email.toLowerCase().includes(t);
    const matchPerfil = perfilFiltro === "todos" || u.perfil.toLowerCase() === perfilFiltro;
    return matchTermo && matchPerfil;
  });
}

function mensagemErro(err: unknown, padrao: string): string {
  return err instanceof Error ? err.message : padrao;
}

function useUsuariosAdmin(token: string | null, isCurrentAdmin: boolean) {
  const [chaves, setChaves] = useState<Record<number, ChaveParceiroAtiva>>({});
  const [chaveGerada, setChaveGerada] = useState<ChaveParceiroGerada | null>(null);
  const [chaveEmAndamento, setChaveEmAndamento] = useState<number | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Nao toca estado antes do primeiro `await`: este loader roda a partir de um
  // efeito, onde setState sincrono dispara render em cascata
  // (react-hooks/set-state-in-effect). Os caminhos interativos ligam o spinner
  // no proprio handler.
  const carregarUsuarios = async () => {
    try {
      const [data, ativas] = await Promise.all([
        fetchUsers(),
        // Falha ao listar as chaves não impede a lista de usuários.
        fetchChavesParceiros(token).catch(() => [] as ChaveParceiroAtiva[]),
      ]);
      setUsers(data);
      setChaves(Object.fromEntries(ativas.map((c) => [c.cliente_id, c])));
      setError(null);
    } catch (err: unknown) {
      setError(mensagemErro(err, "Erro ao carregar usuários."));
    } finally {
      setLoading(false);
    }
  };

  const gerarChave = async (clienteId: number, regenerar: boolean) => {
    if (regenerar && !window.confirm("Gerar uma nova chave revoga a atual. Continuar?")) return;
    setChaveEmAndamento(clienteId);
    try {
      setChaveGerada(await gerarChaveParceiro(token, clienteId));
      setError(null);
      await carregarUsuarios();
    } catch (err: unknown) {
      setError(mensagemErro(err, "Erro ao gerar a chave B2B."));
    } finally {
      setChaveEmAndamento(null);
    }
  };

  const revogarChave = async (clienteId: number) => {
    if (
      !window.confirm("Revogar a chave B2B deste parceiro? O acesso dele ao MCP deixa de valer.")
    ) {
      return;
    }
    setChaveEmAndamento(clienteId);
    try {
      await revogarChaveParceiro(token, clienteId);
      setError(null);
      await carregarUsuarios();
    } catch (err: unknown) {
      setError(mensagemErro(err, "Erro ao revogar a chave B2B."));
    } finally {
      setChaveEmAndamento(null);
    }
  };

  useEffect(() => {
    if (isCurrentAdmin) {
      // Falso positivo: `carregarUsuarios` so toca estado depois de `await fetchUsers`
      // (funcao `async` importada), logo nao ha setState sincrono aqui. A regra
      // nao resolve a assincronia da chamada e assume o pior caso.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregarUsuarios();
    }
  }, [isCurrentAdmin]);
  const acoes: AcoesChave = {
    emAndamento: chaveEmAndamento,
    onGerar: gerarChave,
    onRevogar: revogarChave,
  };

  return { users, chaves, loading, error, chaveGerada, setChaveGerada, acoes };
}

export default function AdminUsuariosPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const [termo, setTermo] = useState("");
  const [perfilFiltro, setPerfilFiltro] = useState<string>("todos");

  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";
  const { users, chaves, loading, error, chaveGerada, setChaveGerada, acoes } = useUsuariosAdmin(
    token,
    isCurrentAdmin,
  );

  if (!currentUser || !isCurrentAdmin) return <AcessoRestrito />;

  const usuariosFiltrados = filtrarUsuarios(users, termo, perfilFiltro.toLowerCase());

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10 space-y-6">
      <UsuariosCabecalho />
      <MetricasUsuarios users={users} />
      <FiltrosUsuarios
        termo={termo}
        onTermo={setTermo}
        perfil={perfilFiltro}
        onPerfil={setPerfilFiltro}
      />

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-500">Carregando usuários...</div>
      ) : usuariosFiltrados.length === 0 ? (
        <UsuariosVazio />
      ) : (
        <UsuariosTabela users={usuariosFiltrados} chaves={chaves} acoes={acoes} />
      )}
      {chaveGerada && <ChaveB2bDialog chave={chaveGerada} onFechar={() => setChaveGerada(null)} />}
    </div>
  );
}

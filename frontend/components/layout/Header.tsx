import Link from "next/link";

const NAV_LINKS = [
  { href: "/", label: "Início" },
  { href: "/produtos", label: "Produtos" },
  { href: "/pedidos", label: "Pedidos" },
  { href: "/agendamentos", label: "Agendamentos" },
  { href: "/suporte", label: "Suporte" },
  { href: "/contato", label: "Contato" },
  { href: "/conta/login", label: "Entrar" },
];

export default function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-gray-900">
          Empresa Fictícia TCC
        </Link>
        <nav aria-label="Navegação principal">
          <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-gray-700">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="hover:text-blue-600 hover:underline">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}

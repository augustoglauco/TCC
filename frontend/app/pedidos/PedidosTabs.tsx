"use client";

interface PedidosTabsProps {
  activeTab: "carrinho" | "cotacao_b2b";
  cartCount: number;
  onChange: (tab: "carrinho" | "cotacao_b2b") => void;
}

export function PedidosTabs({ activeTab, cartCount, onChange }: PedidosTabsProps) {
  const tabCls = (tab: "carrinho" | "cotacao_b2b") =>
    `pb-3 text-sm font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
      activeTab === tab
        ? "border-blue-600 text-blue-600"
        : "border-transparent text-slate-500 hover:text-slate-800"
    }`;

  return (
    <div className="flex border-b border-slate-200 gap-4">
      <button type="button" onClick={() => onChange("carrinho")} className={tabCls("carrinho")}>
        <span>🛒 Meu Carrinho &amp; Checkout</span>
        {cartCount > 0 && (
          <span className="rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-xs font-bold">
            {cartCount}
          </span>
        )}
      </button>

      <button
        type="button"
        onClick={() => onChange("cotacao_b2b")}
        className={tabCls("cotacao_b2b")}
      >
        <span>🏢 Simulador B2B (Preços por Volume)</span>
      </button>
    </div>
  );
}

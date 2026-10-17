"use client";

function valorFormatado(val: number): string {
  return `R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

interface ProductCardPriceProps {
  preco: number;
  precoPromocional?: number | null;
}

export function ProductCardPrice({ preco, precoPromocional }: ProductCardPriceProps) {
  return (
    <div className="mt-4 flex items-baseline justify-end gap-2 text-right">
      {precoPromocional ? (
        <>
          <span className="text-lg font-extrabold text-blue-700">
            {valorFormatado(precoPromocional)}
          </span>
          <span className="text-xs text-slate-400 line-through">{valorFormatado(preco)}</span>
        </>
      ) : (
        <span className="text-xl font-extrabold text-blue-700">{valorFormatado(preco)}</span>
      )}
    </div>
  );
}

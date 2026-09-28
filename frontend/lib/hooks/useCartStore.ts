import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface CartItem {
  produtoId: number;
  nome: string;
  preco: number;
  imagemUrl?: string | null;
  quantidade: number;
  centroDistribuicao: string;
}

interface CartState {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (produtoId: number, centroDistribuicao: string) => void;
  updateQuantity: (produtoId: number, centroDistribuicao: string, quantidade: number) => void;
  clearCart: () => void;
  totalItems: () => number;
  totalValue: () => number;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (newItem) => {
        set((state) => {
          const index = state.items.findIndex(
            (i) =>
              i.produtoId === newItem.produtoId &&
              i.centroDistribuicao === newItem.centroDistribuicao
          );
          if (index >= 0) {
            const updated = [...state.items];
            updated[index] = {
              ...updated[index],
              quantidade: updated[index].quantidade + newItem.quantidade,
            };
            return { items: updated };
          }
          return { items: [...state.items, newItem] };
        });
      },
      removeItem: (produtoId, centroDistribuicao) => {
        set((state) => ({
          items: state.items.filter(
            (i) => !(i.produtoId === produtoId && i.centroDistribuicao === centroDistribuicao)
          ),
        }));
      },
      updateQuantity: (produtoId, centroDistribuicao, quantidade) => {
        if (quantidade <= 0) {
          get().removeItem(produtoId, centroDistribuicao);
          return;
        }
        set((state) => ({
          items: state.items.map((i) =>
            i.produtoId === produtoId && i.centroDistribuicao === centroDistribuicao
              ? { ...i, quantidade }
              : i
          ),
        }));
      },
      clearCart: () => set({ items: [] }),
      totalItems: () => get().items.reduce((acc, item) => acc + item.quantidade, 0),
      totalValue: () => get().items.reduce((acc, item) => acc + item.preco * item.quantidade, 0),
    }),
    {
      name: "tcc_shopping_cart",
    }
  )
);

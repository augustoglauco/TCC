import { create } from "zustand";
import { persist } from "zustand/middleware";
import { login as apiLogin } from "@/lib/api/auth";
import { User } from "@/lib/types/auth";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      login: async (email: string, password = "12345") => {
        const response = await apiLogin(email, password);
        set({ user: response.user, token: response.token });
      },
      logout: () => {
        set({ user: null, token: null });
        useChatStore.getState().clearChat();
      },
      setUser: (user: User | null) => {
        set({ user });
      },
    }),
    {
      name: "auth-storage",
    },
  ),
);

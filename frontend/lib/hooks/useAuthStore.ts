import { create } from "zustand";
import { persist } from "zustand/middleware";
import { login as apiLogin } from "@/lib/api/auth";
import { User } from "@/lib/types/auth";
import {
  getUserConversationStorageKey,
  SESSION_STORAGE_KEY,
  useChatStore,
} from "@/lib/hooks/useChatStore";

interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password?: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      login: async (email: string, password = "12345") => {
        const response = await apiLogin(email, password);
        set({ user: response.user, token: response.token });
        const currentConvId = useChatStore.getState().conversationId;
        if (currentConvId && typeof window !== "undefined") {
          try {
            window.localStorage.setItem(
              getUserConversationStorageKey(response.user.email),
              currentConvId,
            );
            window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
          } catch {
            // ignora restrição de storage
          }
        }
      },
      logout: () => {
        const currentUser = get().user;
        if (currentUser?.email && typeof window !== "undefined") {
          try {
            window.localStorage.removeItem(getUserConversationStorageKey(currentUser.email));
          } catch {
            // ignora restrição de storage
          }
        }
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

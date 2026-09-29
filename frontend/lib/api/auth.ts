import { getApiBaseUrl } from "./apiBaseUrl";
import { LoginResponse, User } from "../types/auth";

export async function login(email: string, password = "12345"): Promise<LoginResponse> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const detail = errorData?.detail || "Erro ao realizar login.";
    throw new Error(detail);
  }

  return response.json();
}

export async function register(payload: {
  nome: string;
  email: string;
  password?: string;
  perfil?: string;
  requesterEmail?: string;
}): Promise<LoginResponse> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      nome: payload.nome,
      email: payload.email,
      password: payload.password,
      perfil: payload.perfil,
      requester_email: payload.requesterEmail,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => null);
    const detail = errorData?.detail || "Erro ao realizar cadastro.";
    throw new Error(detail);
  }

  return response.json();
}

export async function fetchCurrentUser(email: string): Promise<User> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/auth/me?email=${encodeURIComponent(email)}`);

  if (!response.ok) {
    throw new Error("Usuário não encontrado.");
  }

  return response.json();
}

export async function fetchUsers(): Promise<User[]> {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}/api/auth/users`);

  if (!response.ok) {
    throw new Error("Erro ao carregar lista de usuários.");
  }

  return response.json();
}

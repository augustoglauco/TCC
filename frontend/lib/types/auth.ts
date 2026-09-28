export interface User {
  id: number;
  email: string;
  nome: string;
  perfil: string;
  perfil_motivo?: string | null;
}

export interface LoginResponse {
  token: string;
  user: User;
}

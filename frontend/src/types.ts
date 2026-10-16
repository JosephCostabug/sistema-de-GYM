export interface AdminSession {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface Empresa {
  id: string;
  nome: string;
  email: string;
  telefone: string;
  endereco: string;
}

export interface Ginasio {
  id: string;
  nome: string;
  endereco: string;
}

export interface Plano {
  id: string;
  nome: string;
  descricao: string;
  max_visitas_semana: number | null;
  max_visitas_mes: number | null;
  hora_inicio: string | null;
  hora_fim: string | null;
  dias_semana: number[];
  duracao_maxima_minutos: number | null;
  ginasios_permitidos: string[];
  ativo: boolean;
}

export interface Cliente {
  id: string;
  nome: string;
  email: string;
  telefone: string;
  plano_id: string;
  assinatura_inicio: string;
  assinatura_fim: string;
  credenciais: Array<{ metodo: string; codigo: string }>;
  ativo: boolean;
}

export interface ApiErrorItem {
  loc?: Array<string | number>;
  msg: string;
}

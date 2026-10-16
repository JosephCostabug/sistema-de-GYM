import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { apiFetch, ApiError } from "./api";
import type {
  AdminSession,
  Cliente,
  Empresa,
  Ginasio,
  Plano,
} from "./types";

type Route = "hoje" | "clientes" | "planos" | "empresa" | "entrar" | "cadastro";
type Theme = "claro" | "escuro";

const routeTitles: Record<Route, string> = {
  hoje: "Visão geral",
  clientes: "Clientes",
  planos: "Planos",
  empresa: "Empresa e ginásios",
  entrar: "Entrar",
  cadastro: "Criar conta",
};

function routeFromHash(): Route {
  const value = window.location.hash.replace(/^#\/?/, "");
  if (value === "clientes" || value === "planos" || value === "empresa") {
    return value;
  }
  if (value === "cadastro") return "cadastro";
  if (value === "entrar") return "entrar";
  return "hoje";
}

function navigate(route: Route) {
  window.location.hash = `/${route}`;
}

function messageFrom(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Ocorreu um erro inesperado. Tente novamente.";
}

function sessionExpired(error: unknown, expire: () => void): string {
  if (error instanceof ApiError && error.status === 401) {
    expire();
    return "A sessão terminou. Entre novamente para continuar.";
  }
  return messageFrom(error);
}

function currentTheme(): Theme {
  const saved = window.localStorage.getItem("g7m-theme");
  if (saved === "claro" || saved === "escuro") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "escuro"
    : "claro";
}

export default function App() {
  const [route, setRoute] = useState<Route>(routeFromHash);
  const [session, setSession] = useState<AdminSession | null>(null);
  const [theme, setTheme] = useState<Theme>(currentTheme);
  const [online, setOnline] = useState(navigator.onLine);
  const [authNotice, setAuthNotice] = useState("");

  useEffect(() => {
    const syncRoute = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("g7m-theme", theme);
  }, [theme]);

  useEffect(() => {
    const setConnection = () => setOnline(navigator.onLine);
    window.addEventListener("online", setConnection);
    window.addEventListener("offline", setConnection);
    return () => {
      window.removeEventListener("online", setConnection);
      window.removeEventListener("offline", setConnection);
    };
  }, []);

  useEffect(() => {
    if (session && (route === "entrar" || route === "cadastro")) navigate("hoje");
  }, [route, session]);

  const expireSession = () => {
    setSession(null);
    setAuthNotice("A sessão terminou. Entre novamente para continuar.");
    navigate("entrar");
  };

  const startSession = (newSession: AdminSession) => {
    setSession(newSession);
    setAuthNotice("");
    navigate("hoje");
  };

  if (!session) {
    return (
      <PublicLayout theme={theme} onToggleTheme={() => setTheme(toggleTheme(theme))}>
        <AuthPage
          route={route === "cadastro" ? "cadastro" : "entrar"}
          notice={authNotice}
          onSession={startSession}
        />
      </PublicLayout>
    );
  }

  return (
    <ApplicationShell
      route={route}
      online={online}
      theme={theme}
      onToggleTheme={() => setTheme(toggleTheme(theme))}
      onSignOut={() => {
        setSession(null);
        setAuthNotice("");
        navigate("entrar");
      }}
    >
      {route === "clientes" ? (
        <ClientesPage token={session.access_token} onExpired={expireSession} />
      ) : route === "planos" ? (
        <PlanosPage token={session.access_token} onExpired={expireSession} />
      ) : route === "empresa" ? (
        <EmpresaPage token={session.access_token} onExpired={expireSession} />
      ) : (
        <HojePage onNavigate={navigate} />
      )}
    </ApplicationShell>
  );
}

function toggleTheme(theme: Theme): Theme {
  return theme === "claro" ? "escuro" : "claro";
}

function ThemeButton({
  theme,
  onClick,
}: {
  theme: Theme;
  onClick: () => void;
}) {
  return (
    <button className="button button-secondary theme-button" type="button" onClick={onClick}>
      Tema {theme === "claro" ? "escuro" : "claro"}
    </button>
  );
}

function PublicLayout({
  theme,
  onToggleTheme,
  children,
}: {
  theme: Theme;
  onToggleTheme: () => void;
  children: ReactNode;
}) {
  return (
    <div className="public-layout">
      <header className="public-header">
        <a className="wordmark" href="#/entrar" aria-label="G7M, página inicial">
          G7M
        </a>
        <ThemeButton theme={theme} onClick={onToggleTheme} />
      </header>
      {children}
      <footer className="public-footer">Gestão de ginásios</footer>
    </div>
  );
}

function AuthPage({
  route,
  notice,
  onSession,
}: {
  route: "entrar" | "cadastro";
  notice: string;
  onSession: (session: AdminSession) => void;
}) {
  const [error, setError] = useState(notice);
  const [pending, setPending] = useState(false);
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const isSignup = route === "cadastro";

  useEffect(() => setError(notice), [notice]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    setError("");
    if (isSignup && password !== passwordConfirm) {
      setError("As palavras-passe não coincidem.");
      return;
    }
    setPending(true);
    try {
      const session = isSignup
        ? await apiFetch<AdminSession & { empresa: Empresa; ginasio: Ginasio }>(
            "/admin/register",
            {
              method: "POST",
              body: JSON.stringify({
                empresa: {
                  nome: String(form.get("empresa") ?? "").trim(),
                  email: String(form.get("empresaEmail") ?? "").trim(),
                  telefone: String(form.get("telefone") ?? "").trim(),
                  endereco: String(form.get("endereco") ?? "").trim(),
                },
                administrador: { email, password },
                ginasio: {
                  nome: String(form.get("ginasio") ?? "").trim(),
                  endereco: String(form.get("ginasioEndereco") ?? "").trim(),
                },
              }),
            },
          )
        : await apiFetch<AdminSession>("/admin/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
      onSession(session);
    } catch (submitError) {
      setError(messageFrom(submitError));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-panel">
      <p className="eyebrow">{isSignup ? "Primeiro acesso" : "Área administrativa"}</p>
      <h1>{isSignup ? "Criar conta da empresa" : "Entrar no G7M"}</h1>
      <p className="intro">
        {isSignup
          ? "Registe a empresa, o administrador e o primeiro ginásio."
          : "Aceda à gestão da sua empresa."}
      </p>
      {error && <p className="notice notice-danger" role="alert">{error}</p>}
      <form className="form-stack" onSubmit={submit}>
        {isSignup && (
          <>
            <FormField label="Nome da empresa" name="empresa" required maxLength={160} />
            <FormField label="Email da empresa" name="empresaEmail" type="email" required />
            <FormField label="Telefone" name="telefone" type="tel" maxLength={80} />
            <FormField label="Endereço da empresa" name="endereco" maxLength={300} />
            <div className="form-divider"><span>Administrador</span></div>
          </>
        )}
        <FormField
          label={isSignup ? "Email de acesso" : "Email"}
          name="email"
          type="email"
          autoComplete="username"
          required
        />
        <FormField
          label="Palavra-passe"
          name="password"
          type="password"
          autoComplete={isSignup ? "new-password" : "current-password"}
          minLength={12}
          maxLength={256}
          required
          hint={isSignup ? "Use pelo menos 12 caracteres." : undefined}
        />
        {isSignup && (
          <>
            <FormField
              label="Confirmar palavra-passe"
              name="passwordConfirm"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={256}
              required
              value={passwordConfirm}
              onChange={(event) => setPasswordConfirm(event.target.value)}
            />
            <div className="form-divider"><span>Primeiro ginásio</span></div>
            <FormField label="Nome do ginásio" name="ginasio" required maxLength={160} />
            <FormField label="Endereço do ginásio" name="ginasioEndereco" maxLength={300} />
          </>
        )}
        <button className="button button-primary button-wide" type="submit" disabled={pending}>
          {pending ? "A processar…" : isSignup ? "Criar conta" : "Entrar"}
        </button>
      </form>
      <p className="auth-switch">
        {isSignup ? "Já tem uma conta?" : "Ainda não tem conta?"}{" "}
        <a href={isSignup ? "#/entrar" : "#/cadastro"}>
          {isSignup ? "Entrar" : "Criar conta da empresa"}
        </a>
      </p>
    </main>
  );
}

function FormField({
  label,
  name,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  name: string;
  hint?: string;
}) {
  const hintId = hint ? `${name}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input id={name} name={name} aria-describedby={hintId} {...props} />
      {hint && <small id={hintId} className="field-hint">{hint}</small>}
    </div>
  );
}

function ApplicationShell({
  route,
  online,
  theme,
  onToggleTheme,
  onSignOut,
  children,
}: {
  route: Route;
  online: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const links: Array<{ route: Route; label: string }> = [
    { route: "hoje", label: "Visão geral" },
    { route: "clientes", label: "Clientes" },
    { route: "planos", label: "Planos" },
    { route: "empresa", label: "Empresa e ginásios" },
  ];

  return (
    <div className="app-shell">
      {menuOpen && (
        <button
          className="menu-backdrop"
          type="button"
          aria-label="Fechar navegação"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside className={`sidebar${menuOpen ? " sidebar-open" : ""}`}>
        <a className="wordmark" href="#/hoje" aria-label="G7M, visão geral">G7M</a>
        <p className="sidebar-label">Gestão</p>
        <nav aria-label="Navegação principal">
          {links.map((link) => (
            <a
              key={link.route}
              className={`nav-link${route === link.route ? " nav-link-active" : ""}`}
              href={`#/${link.route}`}
              aria-current={route === link.route ? "page" : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="connection-status">
            <span className={`status-square ${online ? "status-online" : "status-offline"}`} />
            {online ? "Rede disponível" : "Sem ligação de rede"}
          </p>
          <p className="role-label">Administrador</p>
          <ThemeButton theme={theme} onClick={onToggleTheme} />
          <button className="button button-tertiary signout-button" type="button" onClick={onSignOut}>
            Terminar sessão
          </button>
        </div>
      </aside>
      <main className="main-column">
        <header className="topbar">
          <button
            className="button button-secondary menu-button"
            type="button"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            Menu
          </button>
          <div>
            <p className="eyebrow">G7M</p>
            <h1>{routeTitles[route]}</h1>
          </div>
          <p className="topbar-status" role="status" aria-live="polite">
            <span className={`status-square ${online ? "status-online" : "status-offline"}`} />
            {online ? "Rede disponível" : "Sem ligação de rede"}
          </p>
        </header>
        {!online && (
          <div className="offline-banner" role="status">
            Sem ligação de rede. As alterações não serão guardadas enquanto a ligação não for restabelecida.
          </div>
        )}
        <section className="page-content" aria-labelledby="page-heading">
          <h2 id="page-heading" className="visually-hidden">{routeTitles[route]}</h2>
          {children}
        </section>
      </main>
    </div>
  );
}

function HojePage({ onNavigate }: { onNavigate: (route: Route) => void }) {
  return (
    <div className="content-narrow">
      <p className="eyebrow">Operação</p>
      <h2>Gestão do ginásio</h2>
      <p className="intro">
        Consulte os dados da empresa e continue a tarefa que pretende realizar.
      </p>
      <div className="action-list">
        <button className="action-row" type="button" onClick={() => onNavigate("clientes")}>
          <span>
            <strong>Clientes</strong>
            <small>Consultar e registar clientes com assinatura</small>
          </span>
          <span aria-hidden="true">→</span>
        </button>
        <button className="action-row" type="button" onClick={() => onNavigate("planos")}>
          <span>
            <strong>Planos</strong>
            <small>Definir e actualizar os planos da empresa</small>
          </span>
          <span aria-hidden="true">→</span>
        </button>
        <button className="action-row" type="button" onClick={() => onNavigate("empresa")}>
          <span>
            <strong>Empresa e ginásios</strong>
            <small>Actualizar o perfil e gerir os ginásios</small>
          </span>
          <span aria-hidden="true">→</span>
        </button>
      </div>
      <p className="supporting-note">
        Os indicadores operacionais serão apresentados quando a API disponibilizar esses dados.
      </p>
    </div>
  );
}

function EmpresaPage({
  token,
  onExpired,
}: {
  token: string;
  onExpired: () => void;
}) {
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [ginasios, setGinasios] = useState<Ginasio[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [company, gyms] = await Promise.all([
        apiFetch<Empresa>("/empresa", { token }),
        apiFetch<Ginasio[]>("/ginasios", { token }),
      ]);
      setEmpresa(company);
      setGinasios(gyms);
    } catch (loadError) {
      setError(sessionExpired(loadError, onExpired));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [token]);

  async function updateCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const updated = await apiFetch<Empresa>("/empresa", {
        method: "PATCH",
        token,
        body: JSON.stringify({
          nome: String(form.get("nome") ?? "").trim(),
          email: String(form.get("email") ?? "").trim(),
          telefone: String(form.get("telefone") ?? "").trim(),
          endereco: String(form.get("endereco") ?? "").trim(),
        }),
      });
      setEmpresa(updated);
      setSuccess("Perfil da empresa actualizado.");
    } catch (updateError) {
      setError(sessionExpired(updateError, onExpired));
    } finally {
      setPending(false);
    }
  }

  async function createGym(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setPending(true);
    setError("");
    setSuccess("");
    try {
      await apiFetch<Ginasio>("/ginasios", {
        method: "POST",
        token,
        body: JSON.stringify({
          nome: String(form.get("nome") ?? "").trim(),
          endereco: String(form.get("endereco") ?? "").trim(),
        }),
      });
      formElement.reset();
      await load();
      setSuccess("Ginásio adicionado à empresa.");
    } catch (createError) {
      setError(sessionExpired(createError, onExpired));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="content-narrow">
      <SectionFeedback error={error} success={success} loading={loading} onRetry={load} />
      {empresa && (
        <>
          <section className="section-block">
            <div className="section-heading">
              <div><p className="eyebrow">Perfil</p><h2>Dados da empresa</h2></div>
            </div>
            <form className="form-stack" onSubmit={updateCompany}>
              <FormField label="Nome" name="nome" defaultValue={empresa.nome} required maxLength={160} />
              <FormField label="Email" name="email" type="email" defaultValue={empresa.email} required />
              <FormField label="Telefone" name="telefone" defaultValue={empresa.telefone} maxLength={80} />
              <FormField label="Endereço" name="endereco" defaultValue={empresa.endereco} maxLength={300} />
              <button className="button button-primary" type="submit" disabled={pending}>
                {pending ? "A guardar…" : "Guardar"}
              </button>
            </form>
          </section>
          <section className="section-block">
            <div className="section-heading">
              <div><p className="eyebrow">Estrutura</p><h2>Ginásios</h2></div>
            </div>
            {ginasios.length ? (
              <ul className="record-list">
                {ginasios.map((gym) => (
                  <li key={gym.id}>
                    <strong>{gym.nome}</strong>
                    <span>{gym.endereco || "Sem endereço registado"}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="empty-state">Ainda não há ginásios registados.</p>}
            <form className="form-stack form-after-list" onSubmit={createGym}>
              <h3>Adicionar ginásio</h3>
              <FormField label="Nome do ginásio" name="nome" required maxLength={160} />
              <FormField label="Endereço" name="endereco" maxLength={300} />
              <button className="button button-secondary" type="submit" disabled={pending}>
                Adicionar ginásio
              </button>
            </form>
          </section>
        </>
      )}
    </div>
  );
}

interface PlanoForm {
  nome: string;
  descricao: string;
  max_visitas_semana: string;
  max_visitas_mes: string;
  hora_inicio: string;
  hora_fim: string;
  dias_semana: number[];
  duracao_maxima_minutos: string;
  ginasios_permitidos: string[];
  ativo: boolean;
}

const emptyPlan: PlanoForm = {
  nome: "",
  descricao: "",
  max_visitas_semana: "",
  max_visitas_mes: "",
  hora_inicio: "",
  hora_fim: "",
  dias_semana: [0, 1, 2, 3, 4, 5, 6],
  duracao_maxima_minutos: "",
  ginasios_permitidos: [],
  ativo: true,
};

const weekdayLabels = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];

function PlanosPage({
  token,
  onExpired,
}: {
  token: string;
  onExpired: () => void;
}) {
  const [plans, setPlans] = useState<Plano[]>([]);
  const [gyms, setGyms] = useState<Ginasio[]>([]);
  const [draft, setDraft] = useState<PlanoForm>(emptyPlan);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [planList, gymList] = await Promise.all([
        apiFetch<Plano[]>("/planos", { token }),
        apiFetch<Ginasio[]>("/ginasios", { token }),
      ]);
      setPlans(planList);
      setGyms(gymList);
    } catch (loadError) {
      setError(sessionExpired(loadError, onExpired));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [token]);

  function editPlan(plan: Plano) {
    setEditingId(plan.id);
    setDraft({
      nome: plan.nome,
      descricao: plan.descricao,
      max_visitas_semana: plan.max_visitas_semana?.toString() ?? "",
      max_visitas_mes: plan.max_visitas_mes?.toString() ?? "",
      hora_inicio: plan.hora_inicio?.slice(0, 5) ?? "",
      hora_fim: plan.hora_fim?.slice(0, 5) ?? "",
      dias_semana: plan.dias_semana,
      duracao_maxima_minutos: plan.duracao_maxima_minutos?.toString() ?? "",
      ginasios_permitidos: plan.ginasios_permitidos,
      ativo: plan.ativo,
    });
  }

  async function savePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    const body = {
      nome: draft.nome.trim(),
      descricao: draft.descricao.trim(),
      max_visitas_semana: optionalNumber(draft.max_visitas_semana),
      max_visitas_mes: optionalNumber(draft.max_visitas_mes),
      hora_inicio: draft.hora_inicio ? `${draft.hora_inicio}:00` : null,
      hora_fim: draft.hora_fim ? `${draft.hora_fim}:00` : null,
      dias_semana: draft.dias_semana,
      duracao_maxima_minutos: optionalNumber(draft.duracao_maxima_minutos),
      ginasios_permitidos: draft.ginasios_permitidos,
      ativo: draft.ativo,
    };
    try {
      await apiFetch<Plano>(editingId ? `/planos/${encodeURIComponent(editingId)}` : "/planos", {
        method: editingId ? "PUT" : "POST",
        token,
        body: JSON.stringify(body),
      });
      setEditingId(null);
      setDraft(emptyPlan);
      await load();
      setSuccess(editingId ? "Plano actualizado." : "Plano criado.");
    } catch (saveError) {
      setError(sessionExpired(saveError, onExpired));
    } finally {
      setPending(false);
    }
  }

  const gymNames = useMemo(
    () => new Map(gyms.map((gym) => [gym.id, gym.nome])),
    [gyms],
  );

  return (
    <div className="content-wide">
      <SectionFeedback error={error} success={success} loading={loading} onRetry={load} />
      <section className="section-block">
        <div className="section-heading">
          <div><p className="eyebrow">Ofertas</p><h2>Planos registados</h2></div>
        </div>
        {!loading && plans.length === 0 ? (
          <p className="empty-state">Ainda não há planos. Crie um plano para associar uma assinatura a um cliente.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Plano</th><th>Ginásios</th><th>Limite semanal</th><th>Estado</th><th><span className="visually-hidden">Acções</span></th></tr></thead>
              <tbody>
                {plans.map((plan) => (
                  <tr key={plan.id}>
                    <th scope="row">{plan.nome}<small>{plan.descricao}</small></th>
                    <td data-label="Ginásios">{plan.ginasios_permitidos.map((id) => gymNames.get(id) ?? "Ginásio").join(", ")}</td>
                    <td className="numeric" data-label="Limite semanal">{plan.max_visitas_semana ?? "Sem limite"}</td>
                    <td data-label="Estado"><StateLabel active={plan.ativo} /></td>
                    <td data-label="Acções"><button className="button button-tertiary" type="button" onClick={() => editPlan(plan)}>Editar</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="section-block content-narrow">
        <div className="section-heading">
          <div>
            <p className="eyebrow">{editingId ? "Editar" : "Novo plano"}</p>
            <h2>{editingId ? "Actualizar plano" : "Criar plano"}</h2>
          </div>
          {editingId && <button className="button button-tertiary" type="button" onClick={() => { setEditingId(null); setDraft(emptyPlan); }}>Cancelar edição</button>}
        </div>
        <form className="form-stack" onSubmit={savePlan}>
          <FormField label="Nome do plano" name="plan-name" value={draft.nome} onChange={(event) => setDraft({ ...draft, nome: event.target.value })} required maxLength={100} />
          <div className="field">
            <label htmlFor="plan-description">Descrição</label>
            <textarea id="plan-description" value={draft.descricao} onChange={(event) => setDraft({ ...draft, descricao: event.target.value })} rows={3} />
          </div>
          <div className="form-grid">
            <FormField label="Máximo de visitas por semana" name="plan-weekly" type="number" min={0} value={draft.max_visitas_semana} onChange={(event) => setDraft({ ...draft, max_visitas_semana: event.target.value })} />
            <FormField label="Máximo de visitas por mês" name="plan-monthly" type="number" min={0} value={draft.max_visitas_mes} onChange={(event) => setDraft({ ...draft, max_visitas_mes: event.target.value })} />
            <FormField label="Hora de início" name="plan-start" type="time" value={draft.hora_inicio} onChange={(event) => setDraft({ ...draft, hora_inicio: event.target.value })} />
            <FormField label="Hora de fim" name="plan-end" type="time" value={draft.hora_fim} onChange={(event) => setDraft({ ...draft, hora_fim: event.target.value })} />
            <FormField label="Duração máxima (minutos)" name="plan-duration" type="number" min={1} value={draft.duracao_maxima_minutos} onChange={(event) => setDraft({ ...draft, duracao_maxima_minutos: event.target.value })} />
          </div>
          <fieldset className="choice-group">
            <legend>Dias permitidos</legend>
            <div className="choice-grid">
              {weekdayLabels.map((label, day) => (
                <label className="check-option" key={label}>
                  <input
                    type="checkbox"
                    checked={draft.dias_semana.includes(day)}
                    onChange={() => setDraft({
                      ...draft,
                      dias_semana: draft.dias_semana.includes(day)
                        ? draft.dias_semana.filter((item) => item !== day)
                        : [...draft.dias_semana, day].sort(),
                    })}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="choice-group">
            <legend>Ginásios permitidos</legend>
            {gyms.length ? gyms.map((gym) => (
              <label className="check-option" key={gym.id}>
                <input
                  type="checkbox"
                  checked={draft.ginasios_permitidos.includes(gym.id)}
                  onChange={() => setDraft({
                    ...draft,
                    ginasios_permitidos: draft.ginasios_permitidos.includes(gym.id)
                      ? draft.ginasios_permitidos.filter((id) => id !== gym.id)
                      : [...draft.ginasios_permitidos, gym.id],
                  })}
                />
                {gym.nome}
              </label>
            )) : <p className="field-hint">Registe um ginásio antes de criar planos.</p>}
          </fieldset>
          {editingId && (
            <label className="check-option">
              <input type="checkbox" checked={draft.ativo} onChange={(event) => setDraft({ ...draft, ativo: event.target.checked })} />
              Plano activo
            </label>
          )}
          <button className="button button-primary" type="submit" disabled={pending || gyms.length === 0}>
            {pending ? "A guardar…" : editingId ? "Guardar alterações" : "Criar plano"}
          </button>
        </form>
      </section>
    </div>
  );
}

function optionalNumber(value: string): number | null {
  return value === "" ? null : Number(value);
}

function StateLabel({ active }: { active: boolean }) {
  return (
    <span className="state-label">
      <span className={`status-square ${active ? "status-online" : "status-offline"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function ClientesPage({
  token,
  onExpired,
}: {
  token: string;
  onExpired: () => void;
}) {
  const [clients, setClients] = useState<Cliente[]>([]);
  const [gyms, setGyms] = useState<Ginasio[]>([]);
  const [plans, setPlans] = useState<Plano[]>([]);
  const [gymId, setGymId] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [clientList, gymList, planList] = await Promise.all([
        apiFetch<Cliente[]>("/clientes", { token }),
        apiFetch<Ginasio[]>("/ginasios", { token }),
        apiFetch<Plano[]>("/planos", { token }),
      ]);
      setClients(clientList);
      setGyms(gymList);
      setPlans(planList);
      if (!gymId && gymList.length) setGymId(gymList[0].id);
    } catch (loadError) {
      setError(sessionExpired(loadError, onExpired));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [token]);

  const availablePlans = plans.filter(
    (plan) => plan.ativo && plan.ginasios_permitidos.includes(gymId),
  );
  const visibleClients = clients.filter((client) => {
    const query = search.trim().toLocaleLowerCase("pt-AO");
    return !query || [client.nome, client.email, client.telefone]
      .some((value) => value.toLocaleLowerCase("pt-AO").includes(query));
  });

  async function createClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const created = await apiFetch<Cliente>("/clientes", {
        method: "POST",
        token,
        body: JSON.stringify({
          nome: String(form.get("nome") ?? "").trim(),
          email: String(form.get("email") ?? "").trim(),
          telefone: String(form.get("telefone") ?? "").trim(),
          plano_id: String(form.get("plano") ?? ""),
          assinatura_inicio: localInputToIso(String(form.get("inicio") ?? "")),
          assinatura_fim: localInputToIso(String(form.get("fim") ?? "")),
          credenciais: [{
            metodo: String(form.get("metodo") ?? "cartao"),
            codigo: String(form.get("codigo") ?? "").trim(),
          }],
        }),
      });
      formElement.reset();
      await load();
      setSuccess(`Cliente ${created.nome} registado com assinatura.`);
    } catch (createError) {
      setError(sessionExpired(createError, onExpired));
    } finally {
      setPending(false);
    }
  }

  const initialDates = useMemo(() => {
    const start = new Date();
    const end = new Date(start);
    end.setMonth(end.getMonth() + 1);
    return { start: toLocalInput(start), end: toLocalInput(end) };
  }, []);

  return (
    <div className="content-wide">
      <SectionFeedback error={error} success={success} loading={loading} onRetry={load} />
      <section className="section-block">
        <div className="section-heading">
          <div><p className="eyebrow">Registo</p><h2>Adicionar cliente</h2></div>
        </div>
        {gyms.length === 0 && !loading ? (
          <p className="empty-state">Registe um ginásio antes de adicionar clientes. <a href="#/empresa">Gerir ginásios</a></p>
        ) : (
          <form className="form-stack content-narrow" onSubmit={createClient}>
            <div className="field">
              <label htmlFor="client-gym">Ginásio</label>
              <select id="client-gym" value={gymId} onChange={(event) => setGymId(event.target.value)} required>
                {gyms.map((gym) => <option key={gym.id} value={gym.id}>{gym.nome}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="client-plan">Plano de assinatura</label>
              <select id="client-plan" name="plano" required disabled={availablePlans.length === 0}>
                {availablePlans.length ? (
                  <>
                    <option value="">Seleccione um plano</option>
                    {availablePlans.map((plan) => <option key={plan.id} value={plan.id}>{plan.nome}</option>)}
                  </>
                ) : <option value="">Sem planos activos para este ginásio</option>}
              </select>
              {availablePlans.length === 0 && <small className="field-hint"><a href="#/planos">Criar ou associar um plano</a></small>}
            </div>
            <div className="form-grid">
              <FormField label="Nome" name="nome" autoComplete="name" required maxLength={120} />
              <FormField label="Email" name="email" type="email" autoComplete="email" required />
              <FormField label="Telefone" name="telefone" type="tel" autoComplete="tel" />
              <FormField label="Início da assinatura" name="inicio" type="datetime-local" defaultValue={initialDates.start} required />
              <FormField label="Fim da assinatura" name="fim" type="datetime-local" defaultValue={initialDates.end} required />
              <div className="field">
                <label htmlFor="client-method">Método da credencial</label>
                <select id="client-method" name="metodo">
                  <option value="cartao">Cartão</option>
                  <option value="pin">PIN</option>
                  <option value="qr">QR</option>
                  <option value="biometria">Identificador biométrico</option>
                  <option value="face">Identificador facial</option>
                </select>
              </div>
              <FormField
                label="Código de referência da credencial"
                name="codigo"
                required
                maxLength={250}
                hint="Registe apenas a referência do identificador, nunca dados biométricos."
              />
            </div>
            <button className="button button-primary" type="submit" disabled={pending || availablePlans.length === 0}>
              {pending ? "A registar…" : "Registar cliente"}
            </button>
          </form>
        )}
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div><p className="eyebrow">Registos</p><h2>Clientes da empresa</h2></div>
          <label className="search-field">
            <span className="visually-hidden">Pesquisar clientes</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar por nome, email ou telefone" type="search" />
          </label>
        </div>
        {!loading && visibleClients.length === 0 ? (
          <p className="empty-state">{clients.length ? "Não foram encontrados clientes para esta pesquisa." : "Ainda não há clientes registados."}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Cliente</th><th>Email</th><th>Telefone</th><th>Assinatura até</th><th>Estado</th></tr></thead>
              <tbody>
                {visibleClients.map((client) => (
                  <tr key={client.id}>
                    <th scope="row">{client.nome}</th>
                    <td data-label="Email">{client.email}</td>
                    <td data-label="Telefone">{client.telefone || "—"}</td>
                    <td data-label="Assinatura até">{new Intl.DateTimeFormat("pt-AO").format(new Date(client.assinatura_fim))}</td>
                    <td data-label="Estado"><StateLabel active={client.ativo} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function toLocalInput(date: Date): string {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 16);
}

function localInputToIso(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("Indique uma data válida para a assinatura.");
  return date.toISOString();
}

function SectionFeedback({
  error,
  success,
  loading,
  onRetry,
}: {
  error: string;
  success: string;
  loading: boolean;
  onRetry: () => void;
}) {
  if (loading) {
    return <p className="loading-state" role="status">A carregar dados…</p>;
  }
  return (
    <>
      {error && (
        <div className="notice notice-danger" role="alert">
          <p>{error}</p>
          <button className="button button-secondary" type="button" onClick={onRetry}>Tentar novamente</button>
        </div>
      )}
      {success && <p className="notice notice-success" role="status">{success}</p>}
    </>
  );
}

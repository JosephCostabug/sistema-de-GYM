"""Guarda a URI PostgreSQL Supabase no .env sem mostrar credenciais."""

from getpass import getpass
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def main() -> None:
    """Valida URI Supabase, força TLS e atualiza apenas as variáveis necessárias."""
    valores = dotenv_values(ENV_FILE)
    segredo = valores.get("ADMIN_TOKEN_SECRET", "")
    if len(segredo.encode("utf-8")) < 32:
        raise SystemExit("ADMIN_TOKEN_SECRET ausente ou curto; configure um segredo de 32 bytes.")

    entrada = getpass(
        "Cole a URI completa do Session pooler ou apenas a senha do banco (entrada oculta): "
    ).strip()
    try:
        if entrada.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            url = make_url(entrada)
        else:
            url_atual = valores.get("DATABASE_URL", "")
            url = make_url(url_atual).set(password=entrada)
    except (ValueError, TypeError) as erro:
        raise SystemExit("URI PostgreSQL inválida.") from erro

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise SystemExit("Use uma URI PostgreSQL compatível com Psycopg 3.")
    host = url.host or ""
    if not (host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")):
        raise SystemExit("O host da URI não pertence a um endpoint Supabase.")
    if not url.username or not url.password or not url.database:
        raise SystemExit("A URI precisa conter usuário, senha e nome da base.")

    sslmode = url.query.get("sslmode", "")
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        url = url.update_query_dict({"sslmode": "require"})

    project_ref = _extrair_project_ref(host, url.username)
    linhas = ENV_FILE.read_text(encoding="utf-8").splitlines()
    chaves_atualizadas = ("APP_ENV=", "DATABASE_URL=", "SUPABASE_PROJECT_REF=")
    preservadas = [linha for linha in linhas if not linha.startswith(chaves_atualizadas)]
    preservadas.extend(
        [
            "APP_ENV=production",
            f"DATABASE_URL={url.render_as_string(hide_password=False)}",
        ]
    )
    if project_ref:
        preservadas.append(f"SUPABASE_PROJECT_REF={project_ref}")
    ENV_FILE.write_text("\n".join(preservadas) + "\n", encoding="utf-8")
    print(f"Conexão Supabase configurada para {host}; segredo não exibido.")


def _extrair_project_ref(host: str, username: str) -> str | None:
    if host.startswith("db.") and host.endswith(".supabase.co"):
        return host.removeprefix("db.").removesuffix(".supabase.co")
    if "." in username:
        return username.rsplit(".", maxsplit=1)[-1]
    return None


if __name__ == "__main__":
    main()
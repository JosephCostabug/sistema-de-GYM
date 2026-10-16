"""Seleciona SQLite local e remove URLs remotas do .env sem exibir segredos."""

from pathlib import Path
import sqlite3
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
VARIAVEIS_REMOVIDAS = ("APP_ENV=", "DATABASE_URL=", "SUPABASE_PROJECT_REF=")
sys.path.insert(0, str(ROOT))

from app.data.paths import caminho_banco_padrao


def main() -> None:
    """Preserva o segredo admin, seleciona o arquivo SQLite e limpa URL remota."""
    banco_antigo = ROOT / "gym_presence.db"
    banco_local = caminho_banco_padrao()
    if banco_antigo.is_file() and not banco_local.exists():
        with sqlite3.connect(banco_antigo) as origem:
            with sqlite3.connect(banco_local) as destino:
                origem.backup(destino)

    linhas = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    segredo_admin = next(
        (
            linha
            for linha in linhas
            if linha.startswith("ADMIN_TOKEN_SECRET=")
            and linha.partition("=")[2].strip()
        ),
        None,
    )
    linhas = [
        linha
        for linha in linhas
        if not linha.startswith(VARIAVEIS_REMOVIDAS)
        and not linha.startswith("ADMIN_TOKEN_SECRET=")
    ]
    linhas.extend(
        [
            "APP_ENV=development",
            segredo_admin
            or f"ADMIN_TOKEN_SECRET={secrets.token_urlsafe(48)}",
        ]
    )
    conteudo = "\n".join(linhas) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=ROOT, delete=False
    ) as temporario:
        temporario.write(conteudo)
        caminho_temporario = Path(temporario.name)
    caminho_temporario.replace(ENV_FILE)
    print(".env configurado para SQLite local; valores secretos não foram exibidos.")


if __name__ == "__main__":
    main()
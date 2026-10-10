"""Cria a primeira conta administrativa sem exibir a senha digitada."""

from getpass import getpass
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.data.database import APP_ENV
from app.data import store
from app.data.store import AdministradorJaExiste
from app.services.administracao import gerar_hash_senha


def main() -> None:
    """Provisiona a conta inicial depois de confirmar o endereço e a senha."""
    store.inicializar()
    email_padrao = "" if APP_ENV == "production" else "admin@gym.local"
    email = input(f"Email do administrador [{email_padrao}]: ").strip().lower()
    email = email or email_padrao
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) is None:
        raise SystemExit("Endereço de email inválido.")

    if APP_ENV == "production" and email.endswith("@gym.local"):
        raise SystemExit("Use um email real para a conta administrativa de produção.")

    minimo_senha = 16 if APP_ENV == "production" else 12
    senha = getpass(f"Senha (mínimo de {minimo_senha} caracteres): ")
    confirmacao = getpass("Confirme a senha: ")
    if len(senha) < minimo_senha:
        raise SystemExit(f"A senha deve ter pelo menos {minimo_senha} caracteres.")
    if senha != confirmacao:
        raise SystemExit("As senhas não coincidem.")

    _garantir_segredo_de_sessao()
    try:
        store.criar_primeiro_admin(email, gerar_hash_senha(senha))
    except AdministradorJaExiste:
        raise SystemExit("Já existe uma conta admin. O bootstrap inicial foi bloqueado.")
    print(f"Conta admin criada para {email}.")


def _garantir_segredo_de_sessao() -> None:
    """Gera uma chave local uma vez, sem imprimir nem versionar o segredo."""
    segredo_atual = os.getenv("ADMIN_TOKEN_SECRET", "")
    if APP_ENV == "production":
        if len(segredo_atual.encode("utf-8")) < 32:
            raise SystemExit("Defina ADMIN_TOKEN_SECRET (mínimo de 32 bytes) no gestor de segredos.")
        return
    if segredo_atual:
        return

    env_path = ROOT / ".env"
    segredo = secrets.token_urlsafe(48)
    with env_path.open("a", encoding="utf-8") as arquivo:
        if env_path.exists() and env_path.stat().st_size:
            arquivo.write("\n")
        arquivo.write(f"ADMIN_TOKEN_SECRET={segredo}\n")
    os.environ["ADMIN_TOKEN_SECRET"] = segredo


if __name__ == "__main__":
    main()
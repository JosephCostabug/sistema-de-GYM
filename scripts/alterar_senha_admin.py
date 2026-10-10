"""Altera a senha de uma conta admin sem colocá-la em argumentos do processo."""

from getpass import getpass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.data.database import APP_ENV
from app.data import store
from app.services.administracao import gerar_hash_senha


def main() -> None:
    """Solicita email e senha ocultada e grava apenas o hash novo."""
    email = input("Email da conta admin: ").strip().lower()
    minimo = 16 if APP_ENV == "production" else 12
    senha = getpass(f"Nova senha (mínimo de {minimo} caracteres): ")
    confirmacao = getpass("Confirme a nova senha: ")
    if len(senha) < minimo:
        raise SystemExit(f"A senha deve ter pelo menos {minimo} caracteres.")
    if senha != confirmacao:
        raise SystemExit("As senhas não coincidem.")
    if not store.atualizar_senha_admin(email, gerar_hash_senha(senha)):
        raise SystemExit("Conta admin não encontrada.")
    print(f"Senha atualizada para {email}.")


if __name__ == "__main__":
    main()
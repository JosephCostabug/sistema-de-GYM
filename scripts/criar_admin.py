"""Provisiona localmente uma empresa, seu administrador e primeiro ginásio."""

from getpass import getpass
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv(ROOT / ".env")

from app.data.database import APP_ENV
from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import AdminRegistro, Empresa, EmpresaDados, Ginasio, GinasioCreate
from app.services.administracao import gerar_hash_senha


def main() -> None:
    """Solicita os dados iniciais sem exibir nem persistir a senha em claro."""
    store.inicializar()
    empresa_legada = store.obter_empresa("empresa-legada")
    if empresa_legada and input(
        "Adicionar administrador à empresa migrada? [s/N]: "
    ).strip().lower() in {"s", "sim"}:
        _adicionar_admin(empresa_legada.id)
        return

    nome_empresa = input("Nome da empresa: ").strip()
    email_empresa = input("Email da empresa: ").strip()
    telefone_empresa = input("Telefone da empresa: ").strip()
    endereco_empresa = input("Endereço da empresa: ").strip()
    nome_ginasio = input("Nome do primeiro ginásio: ").strip()
    endereco_ginasio = input("Endereço do primeiro ginásio: ").strip()
    email_admin = input("Email do administrador: ").strip()

    minimo_senha = 16 if APP_ENV == "production" else 12
    senha = getpass(f"Senha (mínimo de {minimo_senha} caracteres): ")
    confirmacao = getpass("Confirme a senha: ")
    if len(senha) < minimo_senha:
        raise SystemExit(f"A senha deve ter pelo menos {minimo_senha} caracteres.")
    if senha != confirmacao:
        raise SystemExit("As senhas não coincidem.")

    try:
        empresa = Empresa(
            id=f"emp-{store.novo_id()}",
            **EmpresaDados(
                nome=nome_empresa,
                email=email_empresa,
                telefone=telefone_empresa,
                endereco=endereco_empresa,
            ).model_dump(),
        )
        administrador = AdminRegistro(email=email_admin, password=senha)
        ginasio = Ginasio(
            id=f"gym-{store.novo_id()}",
            **GinasioCreate(nome=nome_ginasio, endereco=endereco_ginasio).model_dump(),
        )
    except ValidationError as erro:
        raise SystemExit(
            "Dados inválidos: "
            + "; ".join(item["msg"] for item in erro.errors())
        ) from erro

    _garantir_segredo_de_sessao()
    try:
        store.criar_empresa_com_administrador(
            empresa=empresa,
            administrador_id=f"adm-{store.novo_id()}",
            administrador_email=administrador.email,
            password_hash=gerar_hash_senha(administrador.password),
            ginasio=ginasio,
        )
    except RegistroDuplicado as erro:
        raise SystemExit(
            "Já existe uma conta administrativa com esse email."
        ) from erro
    print(f"Empresa {empresa.nome} criada com o ginásio {ginasio.nome}.")


def _adicionar_admin(empresa_id: str) -> None:
    email = input("Email do administrador: ").strip()
    minimo_senha = 16 if APP_ENV == "production" else 12
    senha = getpass(f"Senha (mínimo de {minimo_senha} caracteres): ")
    confirmacao = getpass("Confirme a senha: ")
    if len(senha) < minimo_senha:
        raise SystemExit(f"A senha deve ter pelo menos {minimo_senha} caracteres.")
    if senha != confirmacao:
        raise SystemExit("As senhas não coincidem.")

    try:
        administrador = AdminRegistro(email=email, password=senha)
    except ValidationError as erro:
        raise SystemExit(
            "Dados inválidos: "
            + "; ".join(item["msg"] for item in erro.errors())
        ) from erro

    _garantir_segredo_de_sessao()
    try:
        store.criar_administrador_empresa(
            empresa_id=empresa_id,
            administrador_id=f"adm-{store.novo_id()}",
            email=administrador.email,
            password_hash=gerar_hash_senha(administrador.password),
        )
    except RegistroDuplicado as erro:
        raise SystemExit(
            "Já existe uma conta administrativa com esse email."
        ) from erro
    print("Administrador criado para a empresa migrada.")


def _garantir_segredo_de_sessao() -> None:
    """Gera uma chave local uma vez, sem imprimir nem versionar o segredo."""
    segredo_atual = os.getenv("ADMIN_TOKEN_SECRET", "")
    if APP_ENV == "production":
        if len(segredo_atual.encode("utf-8")) < 32:
            raise SystemExit("Defina ADMIN_TOKEN_SECRET no gestor de segredos.")
        return
    if segredo_atual:
        return

    env_path = ROOT / ".env"
    segredo = secrets.token_urlsafe(48)
    with env_path.open("a", encoding="utf-8") as arquivo:
        if env_path.stat().st_size:
            arquivo.write("\n")
        arquivo.write(f"ADMIN_TOKEN_SECRET={segredo}\n")
    os.environ["ADMIN_TOKEN_SECRET"] = segredo


if __name__ == "__main__":
    main()

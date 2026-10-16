"""Endpoints de login para administradores."""

from fastapi import APIRouter, HTTPException, status

from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import AdminLogin, CadastroEmpresa, Empresa, Ginasio
from app.services.administracao import criar_token, gerar_hash_senha, verificar_senha

router = APIRouter(prefix="/admin", tags=["Administração"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def registar_empresa(dados: CadastroEmpresa) -> dict:
    """Cria uma empresa, a conta proprietária e seu primeiro ginásio."""
    empresa = Empresa(id=f"emp-{store.novo_id()}", **dados.empresa.model_dump())
    ginasio = Ginasio(id=f"gym-{store.novo_id()}", **dados.ginasio.model_dump())
    administrador_id = f"adm-{store.novo_id()}"
    token, validade = criar_token(administrador_id)
    try:
        store.criar_empresa_com_administrador(
            empresa=empresa,
            administrador_id=administrador_id,
            administrador_email=dados.administrador.email,
            password_hash=gerar_hash_senha(dados.administrador.password),
            ginasio=ginasio,
        )
    except RegistroDuplicado as erro:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta administrativa com esse email.",
        ) from erro

    return {
        "empresa": empresa,
        "ginasio": ginasio,
        "access_token": token,
        "token_type": "bearer",
        "expires_in": validade,
    }


@router.post("/login")
def iniciar_sessao(dados: AdminLogin) -> dict[str, str | int]:
    """Valida credenciais e devolve um token de curta duração."""
    admin = store.obter_admin_por_email(dados.email)
    if (
        admin is None
        or not admin["ativo"]
        or not verificar_senha(dados.password, admin["password_hash"])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, validade = criar_token(admin["id"])
    return {"access_token": token, "token_type": "bearer", "expires_in": validade}
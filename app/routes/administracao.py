"""Endpoints de login para administradores."""

from fastapi import APIRouter, HTTPException, status

from app.data import store
from app.models.schemas import AdminLogin
from app.services.administracao import criar_token, verificar_senha

router = APIRouter(prefix="/admin", tags=["Administração"])


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
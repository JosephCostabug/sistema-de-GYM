"""Rotas do perfil privado da empresa autenticada."""

from fastapi import APIRouter, Depends, HTTPException

from app.data import store
from app.models.schemas import Empresa, EmpresaAtualizacao
from app.services.administracao import AdminContext, exigir_administrador

router = APIRouter(prefix="/empresa", tags=["Empresa"])


@router.get("")
def obter_perfil(autenticado: AdminContext = Depends(exigir_administrador)) -> Empresa:
    empresa = store.obter_empresa(autenticado.empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return empresa


@router.patch("")
def atualizar_perfil(
    dados: EmpresaAtualizacao,
    autenticado: AdminContext = Depends(exigir_administrador),
) -> Empresa:
    empresa = store.atualizar_empresa(
        autenticado.empresa_id,
        dados.model_dump(exclude_unset=True),
    )
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return empresa

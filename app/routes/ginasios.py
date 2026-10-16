"""Rotas de consulta e gestão dos ginásios da empresa autenticada."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import Ginasio, GinasioCreate
from app.services.administracao import AdminContext, exigir_administrador

router = APIRouter(prefix="/ginasios", tags=["Ginásios"])


@router.get("")
def listar_ginasios(autenticado: AdminContext = Depends(exigir_administrador)):
    return store.listar_ginasios(autenticado.empresa_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_ginasio(
    dados: GinasioCreate,
    autenticado: AdminContext = Depends(exigir_administrador),
):
    """Cadastra uma unidade para a empresa autenticada."""
    ginasio = Ginasio(id=f"gym-{store.novo_id()}", **dados.model_dump())
    try:
        return store.criar_ginasio(ginasio, autenticado.empresa_id)
    except RegistroDuplicado as erro:
        raise HTTPException(status_code=409, detail="Ginásio já registado") from erro

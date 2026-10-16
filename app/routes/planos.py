"""Rotas de consulta, criação e personalização de planos."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import Plano, PlanoCreate
from app.services.administracao import AdminContext, exigir_administrador

router = APIRouter(prefix="/planos", tags=["Planos"])


@router.get("")
def listar_planos(autenticado: AdminContext = Depends(exigir_administrador)):
    return store.listar_planos(autenticado.empresa_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_plano(
    dados: PlanoCreate,
    autenticado: AdminContext = Depends(exigir_administrador),
):
    validar_ginasios(dados.ginasios_permitidos, autenticado.empresa_id)
    plano = Plano(id=f"plano-{store.novo_id()}", **dados.model_dump())
    try:
        return store.criar_plano(plano, autenticado.empresa_id)
    except RegistroDuplicado as erro:
        raise HTTPException(status_code=409, detail="Plano já registado") from erro


@router.get("/{plano_id}")
def obter_plano(
    plano_id: str,
    autenticado: AdminContext = Depends(exigir_administrador),
):
    plano = store.obter_plano(plano_id, autenticado.empresa_id)
    if plano is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano


@router.put("/{plano_id}")
def atualizar_plano(
    plano_id: str,
    dados: PlanoCreate,
    autenticado: AdminContext = Depends(exigir_administrador),
):
    if store.obter_plano(plano_id, autenticado.empresa_id) is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    validar_ginasios(dados.ginasios_permitidos, autenticado.empresa_id)
    plano = store.atualizar_plano(
        plano_id,
        autenticado.empresa_id,
        dados.model_dump(),
    )
    if plano is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano


def validar_ginasios(ginasios_permitidos: list[str], empresa_id: str) -> None:
    if not ginasios_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Associe pelo menos um ginásio da empresa ao plano.",
        )
    ids_existentes = {
        ginasio.id for ginasio in store.listar_ginasios(empresa_id)
    }
    if any(ginasio_id not in ids_existentes for ginasio_id in ginasios_permitidos):
        raise HTTPException(status_code=404, detail="Ginásio não encontrado")

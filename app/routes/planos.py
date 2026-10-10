"""Rotas de consulta, criação e personalização de planos."""

from fastapi import APIRouter, Depends, HTTPException

from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import Plano, PlanoCreate
from app.services.administracao import exigir_administrador

router = APIRouter(prefix="/planos", tags=["Planos"])


@router.get("")
def listar_planos():
    return store.listar_planos()


@router.post("")
def criar_plano(dados: PlanoCreate, _: None = Depends(exigir_administrador)):
    validar_ginasios(dados.ginasios_permitidos)
    plano = Plano(id=f"plano-{store.novo_id()}", **dados.model_dump())
    try:
        return store.criar_plano(plano)
    except RegistroDuplicado as erro:
        raise HTTPException(status_code=409, detail="Plano já registado") from erro


@router.get("/{plano_id}")
def obter_plano(plano_id: str):
    plano = store.obter_plano(plano_id)
    if plano is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano


@router.put("/{plano_id}")
def atualizar_plano(
    plano_id: str,
    dados: PlanoCreate,
    _: None = Depends(exigir_administrador),
):
    if store.obter_plano(plano_id) is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    validar_ginasios(dados.ginasios_permitidos)
    plano = store.atualizar_plano(plano_id, dados.model_dump())
    if plano is None:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano


def validar_ginasios(ginasios_permitidos: list[str]) -> None:
    ids_existentes = {ginasio.id for ginasio in store.listar_ginasios()}
    if any(ginasio_id not in ids_existentes for ginasio_id in ginasios_permitidos):
        raise HTTPException(status_code=400, detail="Ginásio permitido inválido")

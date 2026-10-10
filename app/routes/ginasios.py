"""Rotas públicas de consulta aos ginásios cadastrados."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.data import store
from app.data.store import RegistroDuplicado
from app.models.schemas import Ginasio, GinasioCreate
from app.services.administracao import exigir_administrador

router = APIRouter(prefix="/ginasios", tags=["Ginásios"])


@router.get("")
def listar_ginasios():
    return store.listar_ginasios()


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_ginasio(dados: GinasioCreate, _: None = Depends(exigir_administrador)):
    """Cadastra ginásio para configuração inicial ou expansão da operação."""
    ginasio = Ginasio(id=f"gym-{store.novo_id()}", **dados.model_dump())
    try:
        return store.criar_ginasio(ginasio)
    except RegistroDuplicado as erro:
        raise HTTPException(status_code=409, detail="Ginásio já registado") from erro

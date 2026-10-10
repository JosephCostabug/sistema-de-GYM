"""Rotas para marcação e consulta administrativa de presenças."""

from fastapi import APIRouter, Depends, HTTPException

from app.data import store
from app.models.schemas import MarcacaoRequest
from app.services.administracao import exigir_administrador
from app.services.acesso import AcessoNegado, marcar

router = APIRouter(prefix="/presencas", tags=["Presenças"])


@router.post("/marcar")
def marcar_presenca(pedido: MarcacaoRequest):
    try:
        return marcar(
            ginasio_id=pedido.ginasio_id,
            metodo=pedido.metodo,
            credencial=pedido.credencial,
            tipo=pedido.tipo,
        )
    except AcessoNegado as erro:
        raise HTTPException(status_code=403, detail=erro.motivo) from erro


@router.get("")
def listar_presencas(_: None = Depends(exigir_administrador)):
    return [
        {
            **presenca.model_dump(),
            "cliente": cliente,
            "ginasio": ginasio,
            "aberta": presenca.saida_em is None,
        }
        for presenca, cliente, ginasio in store.listar_presencas()
    ]

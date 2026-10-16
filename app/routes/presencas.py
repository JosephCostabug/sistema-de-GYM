"""Rotas para marcação e consulta administrativa de presenças."""

from fastapi import APIRouter, Depends, HTTPException

from app.data import store
from app.models.schemas import MarcacaoRequest
from app.services.administracao import AdminContext, exigir_administrador
from app.services.acesso import AcessoNegado, marcar

router = APIRouter(prefix="/presencas", tags=["Presenças"])


@router.post("/marcar")
def marcar_presenca(
    pedido: MarcacaoRequest,
    autenticado: AdminContext = Depends(exigir_administrador),
):
    ginasio = store.obter_ginasio(pedido.ginasio_id, autenticado.empresa_id)
    if ginasio is None:
        raise HTTPException(status_code=404, detail="Ginásio não encontrado.")

    try:
        return marcar(
            ginasio=ginasio,
            metodo=pedido.metodo,
            credencial=pedido.credencial,
            tipo=pedido.tipo,
            empresa_id=autenticado.empresa_id,
        )
    except AcessoNegado as erro:
        raise HTTPException(status_code=403, detail=erro.motivo) from erro


@router.get("")
def listar_presencas(autenticado: AdminContext = Depends(exigir_administrador)):
    return [
        {
            **presenca.model_dump(),
            "cliente": cliente,
            "ginasio": ginasio,
            "aberta": presenca.saida_em is None,
        }
        for presenca, cliente, ginasio in store.listar_presencas(
            autenticado.empresa_id
        )
    ]

"""Rotas administrativas de cadastro e gestão de clientes/assinaturas."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.data import store
from app.models.schemas import AssinaturaUpdate, Cliente, ClienteCreate
from app.data.store import RegistroDuplicado
from app.services.administracao import exigir_administrador
from app.services.acesso import plano_do_cliente, uso_do_plano

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("")
def listar_clientes(_: None = Depends(exigir_administrador)):
    return store.listar_clientes()


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_cliente(dados: ClienteCreate, _: None = Depends(exigir_administrador)):
    """Cria cliente e credenciais na mesma transação do banco."""
    if store.obter_plano(dados.plano_id) is None:
        raise HTTPException(status_code=400, detail="Plano inválido")
    if store.email_em_uso(dados.email):
        raise HTTPException(status_code=409, detail="Email já registado")
    credenciais = {(item.metodo, item.codigo.strip()) for item in dados.credenciais}
    credenciais_existentes = store.credenciais_em_uso()
    if len(credenciais) != len(dados.credenciais) or credenciais & credenciais_existentes:
        raise HTTPException(status_code=409, detail="Credencial já registada")
    cliente = Cliente(id=f"cli-{store.novo_id()}", **dados.model_dump())
    try:
        return store.criar_cliente(cliente)
    except RegistroDuplicado as erro:
        raise HTTPException(status_code=409, detail="Email ou credencial já registados") from erro


@router.get("/{cliente_id}")
def obter_cliente(cliente_id: str, _: None = Depends(exigir_administrador)):
    cliente = store.obter_cliente(cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    plano = plano_do_cliente(cliente)
    return {
        **cliente.model_dump(),
        "plano": plano,
        "uso_plano": uso_do_plano(cliente, plano, datetime.now().astimezone()),
    }


@router.patch("/{cliente_id}/assinatura")
def atualizar_assinatura(
    cliente_id: str,
    dados: AssinaturaUpdate,
    _: None = Depends(exigir_administrador),
):
    cliente = store.obter_cliente(cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    atualizacao = dados.model_dump(exclude_unset=True)
    plano_id = atualizacao.get("plano_id", cliente.plano_id)
    if store.obter_plano(plano_id) is None:
        raise HTTPException(status_code=400, detail="Plano inválido")

    inicio = atualizacao.get("assinatura_inicio", cliente.assinatura_inicio)
    fim = atualizacao.get("assinatura_fim", cliente.assinatura_fim)
    if (inicio.utcoffset() is None) != (fim.utcoffset() is None):
        raise HTTPException(
            status_code=422,
            detail="As datas da assinatura devem usar o mesmo fuso horário.",
        )
    if inicio >= fim:
        raise HTTPException(
            status_code=422,
            detail="O início da assinatura deve ser anterior ao fim.",
        )

    cliente_atualizado = store.atualizar_assinatura(cliente_id, atualizacao)
    if cliente_atualizado is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return cliente_atualizado

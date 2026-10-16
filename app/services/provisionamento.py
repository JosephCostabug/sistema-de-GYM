"""Orquestração repetível do cadastro inicial em plano de controlo e base da empresa."""

from dataclasses import dataclass
from pathlib import Path

from app.data.control_plane import (
    EmpresaControlo,
    ErroPlanoControlo,
    EstadoProvisionamento,
    PlanoControlo,
)
from app.data.tenant_databases import GestorBasesEmpresa, VERSAO_ESQUEMA_EMPRESA
from app.models.schemas import Empresa, Ginasio


class ErroProvisionamento(Exception):
    """Erro explícito de identidade ou estado no provisionamento da empresa."""


@dataclass(frozen=True)
class ResultadoProvisionamento:
    empresa_id: str
    estado: EstadoProvisionamento
    versao_esquema: int
    caminho_base_dados: Path


def provisionar_empresa(
    controlo: PlanoControlo,
    bases_empresa: GestorBasesEmpresa,
    empresa: Empresa,
    administrador_id: str,
    administrador_email: str,
    password_hash: str,
    ginasio: Ginasio,
) -> ResultadoProvisionamento:
    try:
        registo = controlo.iniciar_provisionamento(
            empresa_id=empresa.id,
            nome=empresa.nome,
            email=empresa.email,
            telefone=empresa.telefone,
            endereco=empresa.endereco,
            administrador_id=administrador_id,
            administrador_email=administrador_email,
            password_hash=password_hash,
        )
    except ErroPlanoControlo as erro:
        raise ErroProvisionamento(str(erro)) from erro

    try:
        caminho = bases_empresa.provisionar(
            chave_base_dados=registo.chave_base_dados,
            ginasio_id=ginasio.id,
            nome_ginasio=ginasio.nome,
            endereco_ginasio=ginasio.endereco,
            proprietario_id=administrador_id,
        )
    except Exception:
        if registo.estado != EstadoProvisionamento.ATIVO:
            controlo.marcar_falhou(empresa.id, "tenant_provisioning_failed")
        raise

    atualizado = controlo.marcar_ativo(empresa.id, VERSAO_ESQUEMA_EMPRESA)
    return ResultadoProvisionamento(
        empresa_id=atualizado.id,
        estado=atualizado.estado,
        versao_esquema=VERSAO_ESQUEMA_EMPRESA,
        caminho_base_dados=caminho,
    )

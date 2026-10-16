"""Persistência local isolada dos metadados de provisionamento da plataforma."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import re

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class EstadoProvisionamento(StrEnum):
    PROVISIONANDO = "provisionando"
    ATIVO = "ativo"
    FALHOU = "falhou"
    SUSPENSO = "suspenso"


class ErroPlanoControlo(Exception):
    """Erro explícito ao criar ou atualizar metadados do plano de controlo."""


class BaseControlo(DeclarativeBase):
    pass


class EmpresaControloRecord(BaseControlo):
    __tablename__ = "empresas"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('provisionando', 'ativo', 'falhou', 'suspenso')",
            name="ck_empresas_estado_provisionamento",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    telefone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    endereco: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    chave_base_dados: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    versao_esquema: Mapped[int | None] = mapped_column(Integer)
    erro_provisionamento: Mapped[str | None] = mapped_column(String(80))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UtilizadorControloRecord(BaseControlo):
    __tablename__ = "utilizadores"
    __table_args__ = (
        CheckConstraint("papel IN ('proprietario', 'administrador')", name="ck_utilizadores_papel"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    papel: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class EmpresaControlo:
    id: str
    nome: str
    email: str
    estado: EstadoProvisionamento
    chave_base_dados: str
    versao_esquema: int | None
    erro_provisionamento: str | None


@dataclass(frozen=True)
class UtilizadorControlo:
    id: str
    empresa_id: str
    email: str
    password_hash: str
    papel: str
    ativo: bool


class PlanoControlo:
    """Acesso ao catálogo central em SQLite para desenvolvimento e testes."""

    def __init__(self, database_url: str):
        url = make_url(database_url)
        if url.drivername not in {"sqlite", "sqlite+pysqlite"}:
            raise ValueError("O plano de controlo local requer uma URL SQLite.")
        if url.database not in {None, "", ":memory:"}:
            caminho = Path(url.database).expanduser()
            caminho.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(caminho.resolve()))

        opcoes: dict = {"pool_pre_ping": True}
        if url.database in {None, "", ":memory:"}:
            opcoes["poolclass"] = StaticPool
        opcoes["connect_args"] = {"check_same_thread": False, "timeout": 10}
        self.engine = create_engine(url, **opcoes)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def inicializar(self) -> None:
        BaseControlo.metadata.create_all(bind=self.engine)

    def iniciar_provisionamento(
        self,
        empresa_id: str,
        nome: str,
        email: str,
        telefone: str,
        endereco: str,
        administrador_id: str,
        administrador_email: str,
        password_hash: str,
    ) -> EmpresaControlo:
        email_normalizado = administrador_email.strip().lower()
        try:
            with self.SessionLocal.begin() as session:
                empresa = session.get(EmpresaControloRecord, empresa_id)
                if empresa is None:
                    empresa = EmpresaControloRecord(
                        id=empresa_id,
                        nome=nome,
                        email=email,
                        telefone=telefone,
                        endereco=endereco,
                        estado=EstadoProvisionamento.PROVISIONANDO.value,
                        chave_base_dados=empresa_id,
                        criado_em=datetime.now(timezone.utc),
                    )
                    session.add(empresa)
                    session.flush()
                    session.add(
                        UtilizadorControloRecord(
                            id=administrador_id,
                            empresa_id=empresa_id,
                            email=email_normalizado,
                            password_hash=password_hash,
                            papel="proprietario",
                            ativo=True,
                            criado_em=datetime.now(timezone.utc),
                        )
                    )
                    session.flush()
                else:
                    if (
                        empresa.nome != nome
                        or empresa.email != email
                        or empresa.telefone != telefone
                        or empresa.endereco != endereco
                    ):
                        raise ErroPlanoControlo(
                            "O identificador da empresa já está associado a outros dados."
                        )
                    utilizador = session.get(UtilizadorControloRecord, administrador_id)
                    if (
                        utilizador is None
                        or utilizador.empresa_id != empresa_id
                        or utilizador.email != email_normalizado
                    ):
                        raise ErroPlanoControlo(
                            "A conta inicial não corresponde à empresa registada."
                        )
                    if empresa.estado == EstadoProvisionamento.SUSPENSO.value:
                        raise ErroPlanoControlo("A empresa está suspensa.")
                    if empresa.estado != EstadoProvisionamento.ATIVO.value:
                        empresa.estado = EstadoProvisionamento.PROVISIONANDO.value
                        empresa.erro_provisionamento = None

                resultado = _empresa_controle(empresa)
        except IntegrityError as erro:
            raise ErroPlanoControlo(
                "O email administrativo ou identificador já está registado."
            ) from erro
        return resultado

    def marcar_ativo(self, empresa_id: str, versao_esquema: int) -> EmpresaControlo:
        return self._atualizar_estado(
            empresa_id,
            EstadoProvisionamento.ATIVO,
            versao_esquema=versao_esquema,
        )

    def marcar_falhou(self, empresa_id: str, codigo_erro: str) -> EmpresaControlo:
        if re.fullmatch(r"[a-z0-9_]{1,80}", codigo_erro) is None:
            raise ValueError("Código de erro de provisionamento inválido.")
        return self._atualizar_estado(
            empresa_id,
            EstadoProvisionamento.FALHOU,
            erro_provisionamento=codigo_erro,
        )

    def obter_empresa(self, empresa_id: str) -> EmpresaControlo | None:
        with self.SessionLocal() as session:
            empresa = session.get(EmpresaControloRecord, empresa_id)
            return None if empresa is None else _empresa_controle(empresa)

    def obter_administrador(self, administrador_id: str) -> UtilizadorControlo | None:
        with self.SessionLocal() as session:
            utilizador = session.get(UtilizadorControloRecord, administrador_id)
            if utilizador is None:
                return None
            return UtilizadorControlo(
                id=utilizador.id,
                empresa_id=utilizador.empresa_id,
                email=utilizador.email,
                password_hash=utilizador.password_hash,
                papel=utilizador.papel,
                ativo=utilizador.ativo,
            )

    def contar_empresas(self) -> int:
        with self.SessionLocal() as session:
            return session.scalar(select(func.count()).select_from(EmpresaControloRecord)) or 0

    def contar_administradores(self) -> int:
        with self.SessionLocal() as session:
            return session.scalar(select(func.count()).select_from(UtilizadorControloRecord)) or 0

    def _atualizar_estado(
        self,
        empresa_id: str,
        estado: EstadoProvisionamento,
        versao_esquema: int | None = None,
        erro_provisionamento: str | None = None,
    ) -> EmpresaControlo:
        with self.SessionLocal.begin() as session:
            empresa = session.get(EmpresaControloRecord, empresa_id)
            if empresa is None:
                raise ErroPlanoControlo("Empresa não encontrada no plano de controlo.")
            empresa.estado = estado.value
            if versao_esquema is not None:
                empresa.versao_esquema = versao_esquema
            empresa.erro_provisionamento = erro_provisionamento
            resultado = _empresa_controle(empresa)
        return resultado


def _empresa_controle(registro: EmpresaControloRecord) -> EmpresaControlo:
    return EmpresaControlo(
        id=registro.id,
        nome=registro.nome,
        email=registro.email,
        estado=EstadoProvisionamento(registro.estado),
        chave_base_dados=registro.chave_base_dados,
        versao_esquema=registro.versao_esquema,
        erro_provisionamento=registro.erro_provisionamento,
    )

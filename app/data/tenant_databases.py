"""Provisionamento SQLite para desenvolvimento e testes das bases por empresa."""

from datetime import datetime, time, timezone
from pathlib import Path
import re

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Time,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


VERSAO_ESQUEMA_EMPRESA = 2


class BaseEmpresa(DeclarativeBase):
    pass


class GinasioEmpresaRecord(BaseEmpresa):
    __tablename__ = "ginasios"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="ck_ginasios_empresa_unico"),
    )

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    endereco: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class MembroEquipaEmpresaRecord(BaseEmpresa):
    __tablename__ = "membros_equipa"
    __table_args__ = (
        CheckConstraint(
            "papel IN ('proprietario', 'administrador', 'gerente')",
            name="ck_membros_equipa_papel",
        ),
    )

    utilizador_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    papel: Mapped[str] = mapped_column(String(20), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlanoEmpresaRecord(BaseEmpresa):
    __tablename__ = "planos"
    __table_args__ = (
        CheckConstraint(
            "max_visitas_semana IS NULL OR max_visitas_semana >= 0",
            name="ck_planos_max_visitas_semana",
        ),
        CheckConstraint(
            "max_visitas_mes IS NULL OR max_visitas_mes >= 0",
            name="ck_planos_max_visitas_mes",
        ),
        CheckConstraint(
            "duracao_maxima_minutos IS NULL OR duracao_maxima_minutos > 0",
            name="ck_planos_duracao",
        ),
        CheckConstraint(
            "hora_inicio IS NULL OR hora_fim IS NULL OR hora_inicio < hora_fim",
            name="ck_planos_horario",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    max_visitas_semana: Mapped[int | None] = mapped_column(Integer)
    max_visitas_mes: Mapped[int | None] = mapped_column(Integer)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fim: Mapped[time | None] = mapped_column(Time)
    dias_semana: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    duracao_maxima_minutos: Mapped[int | None] = mapped_column(Integer)
    ginasio_id: Mapped[str] = mapped_column(
        ForeignKey("ginasios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AssinaturaEmpresaRecord(BaseEmpresa):
    __tablename__ = "assinaturas"
    __table_args__ = (
        UniqueConstraint("cliente_id", "id", name="uq_assinaturas_cliente_id"),
        CheckConstraint("inicio < fim", name="ck_assinaturas_intervalo"),
        CheckConstraint(
            "estado IN ('ativa', 'suspensa', 'terminada')",
            name="ck_assinaturas_estado",
        ),
        Index("ix_assinaturas_cliente", "cliente_id", "inicio"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False
    )
    plano_id: Mapped[str] = mapped_column(
        ForeignKey("planos.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)


class ClienteEmpresaRecord(BaseEmpresa):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("email", name="uq_clientes_email"),
        UniqueConstraint("assinatura_id", name="uq_clientes_assinatura"),
        ForeignKeyConstraint(
            ["id", "assinatura_id"],
            ["assinaturas.cliente_id", "assinaturas.id"],
            name="fk_clientes_assinatura_do_proprio_cliente",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320, collation="NOCASE"), nullable=False)
    telefone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assinatura_id: Mapped[str] = mapped_column(String(80), nullable=False)


class CredencialEmpresaRecord(BaseEmpresa):
    __tablename__ = "credenciais"
    __table_args__ = (
        CheckConstraint(
            "metodo IN ('biometria', 'face', 'cartao', 'pin', 'qr')",
            name="ck_credenciais_metodo",
        ),
        UniqueConstraint("metodo", "codigo", name="uq_credenciais_metodo_codigo"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str] = mapped_column(String(250), nullable=False)


class PresencaEmpresaRecord(BaseEmpresa):
    __tablename__ = "presencas"
    __table_args__ = (
        CheckConstraint("origem IN ('manual', 'dispositivo')", name="ck_presencas_origem"),
        CheckConstraint(
            "autor_tipo IN ('utilizador', 'dispositivo')",
            name="ck_presencas_autor_tipo",
        ),
        CheckConstraint(
            "(origem = 'manual' AND autor_tipo = 'utilizador') OR "
            "(origem = 'dispositivo' AND autor_tipo = 'dispositivo')",
            name="ck_presencas_origem_autor",
        ),
        CheckConstraint(
            "(anulada_em IS NULL AND anulada_por IS NULL AND motivo_anulacao IS NULL) "
            "OR (anulada_em IS NOT NULL AND anulada_por IS NOT NULL "
            "AND motivo_anulacao IS NOT NULL AND length(trim(motivo_anulacao)) > 0)",
            name="ck_presencas_anulacao_justificada",
        ),
        Index(
            "uq_presencas_entrada_aberta_cliente",
            "cliente_id",
            unique=True,
            sqlite_where=text("saida_em IS NULL AND anulada_em IS NULL"),
        ),
        Index("ix_presencas_cliente_entrada", "cliente_id", "entrada_em"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False
    )
    ginasio_id: Mapped[str] = mapped_column(
        ForeignKey("ginasios.id", ondelete="RESTRICT"), nullable=False
    )
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    autor_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    autor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    entrada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hora_local_evento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    saida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulada_por: Mapped[str | None] = mapped_column(String(80))
    motivo_anulacao: Mapped[str | None] = mapped_column(String(1000))


class AuditoriaEmpresaRecord(BaseEmpresa):
    __tablename__ = "auditoria"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    ator_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ator_id: Mapped[str] = mapped_column(String(80), nullable=False)
    acao: Mapped[str] = mapped_column(String(120), nullable=False)
    entidade_tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    entidade_id: Mapped[str] = mapped_column(String(80), nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dados_antes: Mapped[dict | None] = mapped_column(JSON)
    dados_depois: Mapped[dict | None] = mapped_column(JSON)
    motivo: Mapped[str | None] = mapped_column(String(1000))


class VersaoEsquemaEmpresaRecord(BaseEmpresa):
    __tablename__ = "versao_esquema"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="ck_versao_esquema_empresa_unica"),
    )

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)


class ConflitoBaseEmpresa(Exception):
    """A base de dados existente não corresponde ao provisionamento pedido."""


class GestorBasesEmpresa:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).resolve()

    def caminho_para(self, chave_base_dados: str) -> Path:
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", chave_base_dados) is None:
            raise ValueError("Chave de base de dados inválida.")
        return self.raiz / f"{chave_base_dados}.sqlite3"

    def provisionar(
        self,
        chave_base_dados: str,
        ginasio_id: str,
        nome_ginasio: str,
        endereco_ginasio: str,
        proprietario_id: str,
    ) -> Path:
        caminho = self.caminho_para(chave_base_dados)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            URL.create("sqlite", database=str(caminho)),
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        self._configurar_sqlite(engine)

        try:
            tabelas_existentes = set(inspect(engine).get_table_names())
            tabelas_esperadas = set(BaseEmpresa.metadata.tables)
            if not tabelas_existentes:
                BaseEmpresa.metadata.create_all(bind=engine)
            elif tabelas_existentes != tabelas_esperadas:
                raise ConflitoBaseEmpresa(
                    "A base existente não tem o schema tenant esperado; migração necessária."
                )

            with sessionmaker(bind=engine).begin() as session:
                versao = session.get(VersaoEsquemaEmpresaRecord, 1)
                if versao is None:
                    if tabelas_existentes:
                        raise ConflitoBaseEmpresa(
                            "A base existente não tem uma versão de schema válida."
                        )
                    session.add(
                        VersaoEsquemaEmpresaRecord(
                            singleton_id=1,
                            versao=VERSAO_ESQUEMA_EMPRESA,
                        )
                    )
                elif versao.versao != VERSAO_ESQUEMA_EMPRESA:
                    raise ConflitoBaseEmpresa(
                        "A base da empresa requer uma migração de schema."
                    )

                ginasio = session.get(GinasioEmpresaRecord, 1)
                if ginasio is None:
                    session.add(
                        GinasioEmpresaRecord(
                            singleton_id=1,
                            id=ginasio_id,
                            nome=nome_ginasio,
                            endereco=endereco_ginasio,
                        )
                    )
                elif ginasio.id != ginasio_id or (
                    ginasio.nome != nome_ginasio or ginasio.endereco != endereco_ginasio
                ):
                    raise ConflitoBaseEmpresa(
                        "O ginásio existente não corresponde ao pedido de provisionamento."
                    )

                proprietario = session.get(MembroEquipaEmpresaRecord, proprietario_id)
                if proprietario is None:
                    session.add(
                        MembroEquipaEmpresaRecord(
                            utilizador_id=proprietario_id,
                            papel="proprietario",
                            ativo=True,
                            criado_em=datetime.now(timezone.utc),
                        )
                    )
                elif proprietario.papel != "proprietario" or not proprietario.ativo:
                    raise ConflitoBaseEmpresa(
                        "A identidade inicial não é um proprietário ativo nesta base."
                    )

            self._criar_triggers(engine)
            return caminho
        finally:
            engine.dispose()

    @staticmethod
    def _configurar_sqlite(engine) -> None:
        @event.listens_for(engine, "connect")
        def ativar_chaves_estrangeiras(conexao, _registro) -> None:
            conexao.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _criar_triggers(engine) -> None:
        comandos = (
            """
            CREATE TRIGGER IF NOT EXISTS trg_membros_equipa_ultimo_admin_update
            BEFORE UPDATE OF papel, ativo ON membros_equipa
            WHEN OLD.ativo = 1
                AND OLD.papel IN ('proprietario', 'administrador')
                AND (NEW.ativo = 0 OR NEW.papel NOT IN ('proprietario', 'administrador'))
                AND NOT EXISTS (
                    SELECT 1 FROM membros_equipa
                    WHERE utilizador_id != OLD.utilizador_id
                        AND ativo = 1
                        AND papel IN ('proprietario', 'administrador')
                )
            BEGIN
                SELECT RAISE(ABORT, 'a empresa deve manter um administrador ativo');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_membros_equipa_ultimo_admin_delete
            BEFORE DELETE ON membros_equipa
            WHEN OLD.ativo = 1
                AND OLD.papel IN ('proprietario', 'administrador')
                AND NOT EXISTS (
                    SELECT 1 FROM membros_equipa
                    WHERE utilizador_id != OLD.utilizador_id
                        AND ativo = 1
                        AND papel IN ('proprietario', 'administrador')
                )
            BEGIN
                SELECT RAISE(ABORT, 'a empresa deve manter um administrador ativo');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_presencas_immutable_fields
            BEFORE UPDATE OF id, cliente_id, ginasio_id, origem, autor_tipo, autor_id,
                entrada_em, hora_local_evento ON presencas
            BEGIN
                SELECT RAISE(ABORT, 'os dados originais da presença são imutáveis');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_presencas_no_delete
            BEFORE DELETE ON presencas
            BEGIN
                SELECT RAISE(ABORT, 'presenças não podem ser apagadas');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_presencas_saida_once
            BEFORE UPDATE OF saida_em ON presencas
            WHEN (OLD.saida_em IS NOT NULL OR OLD.anulada_em IS NOT NULL)
                AND NEW.saida_em IS NOT OLD.saida_em
            BEGIN
                SELECT RAISE(ABORT, 'a saída de uma presença fechada é imutável');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_presencas_anulacao_once
            BEFORE UPDATE OF anulada_em, anulada_por, motivo_anulacao ON presencas
            WHEN OLD.anulada_em IS NOT NULL
                AND (NEW.anulada_em IS NOT OLD.anulada_em
                    OR NEW.anulada_por IS NOT OLD.anulada_por
                    OR NEW.motivo_anulacao IS NOT OLD.motivo_anulacao)
            BEGIN
                SELECT RAISE(ABORT, 'a anulação de uma presença é imutável');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_auditoria_no_update
            BEFORE UPDATE ON auditoria
            BEGIN
                SELECT RAISE(ABORT, 'o registo de auditoria é append-only');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_auditoria_no_delete
            BEFORE DELETE ON auditoria
            BEGIN
                SELECT RAISE(ABORT, 'o registo de auditoria é append-only');
            END
            """,
        )
        with engine.begin() as connection:
            for comando in comandos:
                connection.exec_driver_sql(comando)

"""Modelos e conexão SQLite local da aplicação."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Time,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from app.data.paths import caminho_banco_padrao

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test"}:
    raise RuntimeError(
        "Este projeto está configurado para SQLite local; use APP_ENV=development ou test."
    )

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = URL.create("sqlite", database=str(caminho_banco_padrao()))
database_url = make_url(DATABASE_URL)
if database_url.drivername not in {"sqlite", "sqlite+pysqlite"}:
    raise RuntimeError("Este projeto usa SQLite. DATABASE_URL deve começar com sqlite://.")

if database_url.database not in {None, "", ":memory:"}:
    database_path = Path(database_url.database).expanduser()
    if not database_path.is_absolute():
        database_path = (PROJECT_ROOT / database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = database_url.set(database=str(database_path))

DATABASE_URL = database_url.render_as_string(hide_password=False)
engine_options: dict = {"pool_pre_ping": True}
if database_url.database in {None, "", ":memory:"}:
    engine_options["poolclass"] = StaticPool
engine_options["connect_args"] = {"check_same_thread": False, "timeout": 10}

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def configurar_sqlite(conexao, _registro) -> None:
    """Ativa chaves estrangeiras e reduz falhas breves por banco ocupado."""
    cursor = conexao.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 10000")
    if database_url.database not in {None, "", ":memory:"}:
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.close()


class Base(DeclarativeBase):
    pass


class CompanyRecord(Base):
    __tablename__ = "empresas"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    telefone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    endereco: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class GymRecord(Base):
    __tablename__ = "ginasios"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    endereco: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class PlanRecord(Base):
    __tablename__ = "planos"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    max_visitas_semana: Mapped[int | None] = mapped_column(Integer)
    max_visitas_mes: Mapped[int | None] = mapped_column(Integer)
    hora_inicio: Mapped[Time | None] = mapped_column(Time)
    hora_fim: Mapped[Time | None] = mapped_column(Time)
    dias_semana: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    duracao_maxima_minutos: Mapped[int | None] = mapped_column(Integer)
    ginasios_permitidos: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClientRecord(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("empresa_id", "email", name="uq_clientes_empresa_email"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    telefone: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    plano_id: Mapped[str] = mapped_column(ForeignKey("planos.id"), nullable=False)
    assinatura_inicio: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    assinatura_fim: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    credenciais: Mapped[list["CredentialRecord"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CredentialRecord(Base):
    __tablename__ = "credenciais"
    __table_args__ = (
        UniqueConstraint("empresa_id", "metodo", "codigo", name="uq_credencial_empresa_metodo_codigo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    codigo: Mapped[str] = mapped_column(String(250), nullable=False)
    cliente: Mapped[ClientRecord] = relationship(back_populates="credenciais")


class AttendanceRecord(Base):
    __tablename__ = "presencas"
    __table_args__ = (
        Index("ix_presencas_cliente_entrada", "cliente_id", "entrada_em"),
        Index(
            "uq_presencas_entrada_aberta_cliente",
            "cliente_id",
            unique=True,
            sqlite_where=text("saida_em IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    ginasio_id: Mapped[str] = mapped_column(ForeignKey("ginasios.id"), nullable=False)
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    entrada_em: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    saida_em: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))


class AdminAccountRecord(Base):
    """Conta administrativa persistida; a senha é armazenada somente como hash."""

    __tablename__ = "contas_admin"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    empresa_id: Mapped[str] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
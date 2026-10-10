"""Modelos relacionais e configuração da conexão com o banco de dados."""

import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


# Permite configuração local por .env sem substituir variáveis já exportadas.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "production"}:
    raise RuntimeError("APP_ENV deve ser development, test ou production.")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV == "production":
        raise RuntimeError("DATABASE_URL é obrigatória em produção.")
    DATABASE_URL = "sqlite:///./gym_presence.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if APP_ENV == "production":
    if not DATABASE_URL.startswith("postgresql+psycopg://"):
        raise RuntimeError("Produção exige PostgreSQL; SQLite é apenas local/teste.")
    sslmode = parse_qs(urlsplit(DATABASE_URL).query).get("sslmode", [""])[0]
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("Configure sslmode=require (ou validação mais forte) em produção.")

engine_options = {"pool_pre_ping": True}
host = urlsplit(DATABASE_URL).hostname or ""
if ".pooler." in host:
    # Evita prepared statements incompatíveis com o pooler transacional do Supabase.
    engine_options["connect_args"] = {"prepare_threshold": None}
if DATABASE_URL.startswith("sqlite"):
    # SQLite é útil para testes locais; PostgreSQL usa pool normal do SQLAlchemy.
    engine_options["connect_args"] = {"check_same_thread": False}
    if ":memory:" in DATABASE_URL or DATABASE_URL.endswith("sqlite://"):
        engine_options["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class GymRecord(Base):
    __tablename__ = "ginasios"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    endereco: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class PlanRecord(Base):
    __tablename__ = "planos"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
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

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
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
    __table_args__ = (UniqueConstraint("metodo", "codigo", name="uq_credencial_metodo_codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    ginasio_id: Mapped[str] = mapped_column(ForeignKey("ginasios.id"), nullable=False)
    metodo: Mapped[str] = mapped_column(String(20), nullable=False)
    entrada_em: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    saida_em: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))


class AdminAccountRecord(Base):
    """Conta administrativa persistida; a senha é armazenada somente como hash."""

    __tablename__ = "contas_admin"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
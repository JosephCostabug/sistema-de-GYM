"""Endpoints de liveness e prontidão para orquestradores de produção."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.data.database import Base, engine

router = APIRouter(prefix="/health", tags=["Saúde"])


@router.get("/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    """Indica que o processo HTTP está ativo, sem depender do banco."""
    return {"status": "alive"}


@router.get("/ready", include_in_schema=False)
def readiness() -> dict[str, str]:
    """Confirma conexão e presença do schema SQLite."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        tabelas = set(inspect(engine).get_table_names())
        obrigatorias = set(Base.metadata.tables)
        if obrigatorias - tabelas:
            raise HTTPException(status_code=503, detail="Schema SQLite incompleto.")
    except SQLAlchemyError as erro:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from erro
    return {"status": "ready"}
"""Endpoints de liveness e prontidão para orquestradores de produção."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.data.database import APP_ENV, engine

router = APIRouter(prefix="/health", tags=["Saúde"])


@router.get("/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    """Indica que o processo HTTP está ativo, sem depender do banco."""
    return {"status": "alive"}


@router.get("/ready", include_in_schema=False)
def readiness() -> dict[str, str]:
    """Confirma conexão e schema antes do balanceador enviar tráfego."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        if APP_ENV == "production":
            tabelas = set(inspect(engine).get_table_names())
            if "alembic_version" not in tabelas:
                raise HTTPException(status_code=503, detail="Banco sem migrations aplicadas.")
    except SQLAlchemyError as erro:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível.") from erro
    return {"status": "ready"}
"""Ponto de entrada da API FastAPI e composição das rotas do ginásio."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.data import store
from app.routes.administracao import router as administracao_router
from app.routes.clientes import router as clientes_router
from app.routes.ginasios import router as ginasios_router
from app.routes.planos import router as planos_router
from app.routes.presencas import router as presencas_router
from app.routes.saude import router as saude_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Cria as tabelas e os dados de exemplo antes de aceitar pedidos."""
    store.inicializar()
    yield


app = FastAPI(
    title="Gym Presence",
    description="Marcação de presença em ginásio por biometria, face, cartão e outros métodos, limitada pelo plano do cliente.",
    lifespan=lifespan,
)

app.include_router(ginasios_router)
app.include_router(administracao_router)
app.include_router(planos_router)
app.include_router(clientes_router)
app.include_router(presencas_router)
app.include_router(saude_router)
